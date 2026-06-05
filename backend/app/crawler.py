import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
import sqlite3
import shutil
import tempfile

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

try:
    import pandas as pd
except ImportError:
    pd = None

logger = logging.getLogger(__name__)

class FileCrawler:
    """Crawls filesystem for sensitive files and extracts text content."""
    
    SCAN_PATHS = {
        'linux': ['~/Downloads', '~/Documents', '~/.config/google-chrome', '~/.mozilla/firefox'],
        'darwin': ['~/Downloads', '~/Documents', '~/Library/Application Support/Google/Chrome', 
                   '~/Library/Application Support/Firefox'],
        'win32': ['~/Downloads', '~/Documents', '~/AppData/Local/Google/Chrome', 
                  '~/AppData/Roaming/Mozilla/Firefox']
    }
    
    HIGH_RISK_PATTERNS = [
        '*_export.*', '*_backup.*', 'statement*.pdf', 'resume*.pdf',
        'tax*.pdf', 'health*.pdf', 'medical*.pdf', '*credentials*',
        '*password*', '*account*'
    ]
    
    SKIPPED_EXTENSIONS = {
        '.exe', '.dll', '.so', '.bin', '.iso', '.dmg',
        '.zip', '.tar', '.gz', '.rar',
        '.png', '.jpg', '.jpeg', '.gif', '.bmp',
        '.mp3', '.mp4', '.mov', '.avi', '.mkv'
    }

    def __init__(self, max_depth: int = 5, max_files: int = 5000):
        self.max_depth = max_depth
        self.max_files = max_files
        self.files_found = []

    def scan(self, directory: str) -> Dict:
        """
        Scan a directory and extract text from files.
        Returns: {files: [...], errors: [...], stats: {...}}
        """
        logger.info(f"Starting crawl of: {directory}")
        results = {
            'files': [],
            'errors': [],
            'stats': {'total_files': 0, 'text_files': 0, 'pdfs': 0, 'csvs': 0, 'dbs': 0}
        }

        try:
            directory = os.path.expanduser(directory)
            if not os.path.isdir(directory):
                raise ValueError(f"Directory not found: {directory}")

            for root, dirs, files in os.walk(directory):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                depth = len(Path(root).relative_to(directory).parts)
                if depth > self.max_depth:
                    continue

                for file in files:
                    if len(results['files']) >= self.max_files:
                        logger.warning(f"Reached max files limit: {self.max_files}")
                        break

                    filepath = os.path.join(root, file)
                    try:
                        results['files'].append(self._process_file(filepath, results['stats']))
                    except Exception as e:
                        logger.error(f"Error processing {filepath}: {e}")
                        results['errors'].append({'file': filepath, 'error': str(e)})

        except Exception as e:
            logger.error(f"Crawl error: {e}")
            results['errors'].append({'crawl': str(e)})

        logger.info(f"Crawl complete: {len(results['files'])} files processed")
        return results

    def _process_file(self, filepath: str, stats: Dict) -> Optional[Dict]:
        """Process a single file and extract text content."""
        stats['total_files'] += 1
        
        ext = os.path.splitext(filepath)[1].lower()
        
        # Skip binary files
        if ext in self.SKIPPED_EXTENSIONS:
            return None

        file_info = {
            'path': filepath,
            'size': os.path.getsize(filepath),
            'modified': os.path.getmtime(filepath),
            'content': '',
            'file_type': self._detect_file_type(filepath),
        }

        try:
            if ext == '.pdf':
                file_info['content'] = self._extract_pdf_text(filepath)
                stats['pdfs'] += 1
            elif ext in ['.csv', '.xlsx']:
                file_info['content'] = self._extract_csv_text(filepath)
                stats['csvs'] += 1
            elif ext == '.json':
                file_info['content'] = self._extract_json_text(filepath)
            elif ext == '.db' or 'sqlite' in filepath.lower():
                file_info['content'] = self._extract_sqlite_text(filepath)
                stats['dbs'] += 1
            elif ext in ['.txt', '.log', '.csv', '.local', '.env'] or self._looks_like_text_config(filepath):
                file_info['content'] = self._extract_plaintext(filepath)
                stats['text_files'] += 1
            else:
                return None  # Unsupported file type

        except Exception as e:
            logger.warning(f"Failed to extract content from {filepath}: {e}")
            return None

        return file_info if file_info['content'] else None

    def _extract_pdf_text(self, filepath: str) -> str:
        """Extract text from PDF file."""
        if fitz:
            try:
                with fitz.open(filepath) as doc:
                    text = ''
                    for page_number, page in enumerate(doc):
                        if page_number >= 10:
                            break
                        text += page.get_text()
                    return text[:5000]
            except Exception as e:
                logger.warning(f"PyMuPDF extraction failed for {filepath}: {e}")

        if not PyPDF2:
            return self._extract_plaintext(filepath)

        try:
            with open(filepath, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                text = ''
                for page in pdf_reader.pages[:10]:  # Limit to first 10 pages
                    text += page.extract_text()
                return text[:5000]  # Limit to first 5000 chars
        except Exception as e:
            logger.error(f"PDF extraction failed for {filepath}: {e}")
            return ''

    def _extract_csv_text(self, filepath: str) -> str:
        """Extract text from CSV/Excel file."""
        if not pd:
            if filepath.endswith('.xlsx'):
                return ''
            return self._extract_plaintext(filepath)

        try:
            if filepath.endswith('.xlsx'):
                df = pd.read_excel(filepath, nrows=100)
            else:
                df = pd.read_csv(filepath, nrows=100)
            return df.to_string()[:5000]
        except Exception as e:
            logger.error(f"CSV extraction failed for {filepath}: {e}")
            return ''

    def _extract_json_text(self, filepath: str) -> str:
        """Extract text from JSON file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return json.dumps(data, indent=2)[:5000]
        except Exception as e:
            logger.error(f"JSON extraction failed for {filepath}: {e}")
            return ''

    def _extract_sqlite_text(self, filepath: str) -> str:
        """Extract text from SQLite database (e.g., Chrome autofill)."""
        tmp_path = None
        conn = None
        try:
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
            tmp_path = tmp_file.name
            tmp_file.close()
            shutil.copy2(filepath, tmp_path)

            conn = sqlite3.connect(tmp_path)
            cursor = conn.cursor()
            
            # Chrome autofill and cookies tables
            tables = ['autofill', 'cookies', 'credit_cards', 'web_app_icons']
            text = ''
            
            for table in tables:
                try:
                    cursor.execute(f"SELECT * FROM {table} LIMIT 50")
                    rows = cursor.fetchall()
                    text += f"\n--- {table} ---\n" + str(rows)[:1000]
                except:
                    pass
            
            return text
        except Exception as e:
            logger.error(f"SQLite extraction failed for {filepath}: {e}")
            return ''
        finally:
            if conn:
                conn.close()
            if tmp_path:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def _extract_plaintext(self, filepath: str) -> str:
        """Extract text from plain text file."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()[:5000]
        except Exception as e:
            logger.error(f"Plaintext extraction failed for {filepath}: {e}")
            return ''

    def _detect_file_type(self, filepath: str) -> str:
        """Detect file type for categorization."""
        ext = os.path.splitext(filepath)[1].lower()
        if ext == '.pdf':
            return 'pdf'
        elif ext in ['.csv', '.xlsx']:
            return 'spreadsheet'
        elif ext == '.json':
            return 'json'
        elif 'chrome' in filepath.lower() or 'firefox' in filepath.lower():
            return 'browser_db'
        else:
            return 'text'

    def _looks_like_text_config(self, filepath: str) -> bool:
        """Detect text-like config files whose final suffix is not enough."""
        name = os.path.basename(filepath).lower()
        return any(marker in name for marker in ['config', 'credentials', 'secrets', 'password'])


# Test the crawler
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    crawler = FileCrawler(max_depth=3, max_files=50)
    test_dir = os.path.expanduser('~/privacylens_test_data')
    
    if os.path.exists(test_dir):
        results = crawler.scan(test_dir)
        print(f"\nOK Crawl complete: {results['stats']['total_files']} files found")
        print(f"OK Content extracted from {len([f for f in results['files'] if f])} files")
        if results['errors']:
            print(f"! {len(results['errors'])} errors")
    else:
        print(f"Test directory not found: {test_dir}")
        print("Create test data and run again")
