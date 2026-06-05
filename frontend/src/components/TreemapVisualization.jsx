import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';

export function TreemapVisualization({ data }) {
  const svgRef = useRef();

  useEffect(() => {
    if (!data || data.length === 0) return;

    // Prepare data for treemap
    const root = d3.hierarchy({ children: data })
      .sum(d => d.size)
      .sort((a, b) => b.value - a.value);

    // Create treemap layout
    const treemap = d3.treemap()
      .size([800, 400])
      .paddingTop(0)
      .paddingRight(2)
      .paddingBottom(2)
      .paddingLeft(2);

    const leaves = treemap(root).leaves();

    // Color scale
    const colorScale = d3.scaleOrdinal()
      .domain(['high', 'medium', 'low'])
      .range(['#FF4136', '#FF851B', '#2ECC40']);

    // Render treemap
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const cells = svg.selectAll('g')
      .data(leaves)
      .enter()
      .append('g')
      .attr('transform', d => `translate(${d.x0},${d.y0})`);

    cells.append('rect')
      .attr('width', d => d.x1 - d.x0)
      .attr('height', d => d.y1 - d.y0)
      .attr('fill', d => colorScale(d.data.severity || 'low'))
      .attr('stroke', '#333')
      .attr('stroke-width', 1);

    cells.append('text')
      .attr('x', 4)
      .attr('y', 20)
      .attr('font-size', '12px')
      .attr('fill', '#fff')
      .text(d => d.data.path.split('/').pop().substring(0, 15));

  }, [data]);

  return (
    <div className="treemap-container">
      <h3>Privacy Risk Heatmap</h3>
      <svg
        ref={svgRef}
        width={800}
        height={400}
        style={{ border: '1px solid #333', borderRadius: '8px' }}
      />
      <div className="legend">
        <span><span className="color-box high"></span> High Risk</span>
        <span><span className="color-box medium"></span> Medium Risk</span>
        <span><span className="color-box low"></span> Low Risk</span>
      </div>
    </div>
  );
}
