import React, { useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import { Button } from './ui/Button';

const formatCurrency = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return null;
  }
  const num = Number(value);
  const abs = Math.abs(num).toLocaleString('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
  return num < 0 ? `-$${abs}` : `$${abs}`;
};

const buildSmoothPath = (coords, yMin = null, yMax = null) => {
  if (coords.length === 0) return '';
  if (coords.length === 1) return `M ${coords[0].x} ${coords[0].y}`;

  const clampY = (y) => {
    let v = y;
    if (yMin !== null && v > yMin) v = yMin;   // SVG y-axis is inverted (lower y = higher value)
    if (yMax !== null && v < yMax) v = yMax;
    return v;
  };

  let path = `M ${coords[0].x} ${coords[0].y}`;
  for (let i = 0; i < coords.length - 1; i += 1) {
    const p0 = coords[i - 1] || coords[i];
    const p1 = coords[i];
    const p2 = coords[i + 1];
    const p3 = coords[i + 2] || p2;

    const cp1x = p1.x + (p2.x - p0.x) / 6;
    let cp1y = p1.y + (p2.y - p0.y) / 6;
    const cp2x = p2.x - (p3.x - p1.x) / 6;
    let cp2y = p2.y - (p3.y - p1.y) / 6;

    if (yMin !== null || yMax !== null) {
      cp1y = clampY(cp1y);
      cp2y = clampY(cp2y);
    }

    path += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x} ${p2.y}`;
  }
  return path;
};



const buildFallbackCostSeries = (baseRatePct) => {
  const base = Math.max(1.2, Math.min(3.8, Number(baseRatePct || 2.2) - 0.55));
  const deltas = [0.02, -0.01, 0.03];
  return [1, 2, 3].map((month, idx) => {
    const mid = base + deltas[idx];
    return { label: `Month ${month}`, mid, lower: mid - 0.08, upper: mid + 0.08 };
  });
};

const SarimaMiniChart = ({ series }) => {
  const [hoveredIndex, setHoveredIndex] = useState(null);
  const points = Array.isArray(series) ? series : [];
  if (!points.length) {
    return null;
  }

  const width = 860;
  const height = 260;
  const left = 44;
  const right = 18;
  const top = 18;
  const bottom = 36;
  const usableW = width - left - right;
  const usableH = height - top - bottom;

  const values = points.flatMap((p) => [Number(p.lower), Number(p.mid), Number(p.upper)]).filter(Number.isFinite);
  let minY = Math.min(...values);
  let maxY = Math.max(...values);
  if (minY === maxY) {
    minY -= 0.1;
    maxY += 0.1;
  }

  const toCoords = (key) => points.map((p, idx) => {
    const x = left + (usableW * (points.length === 1 ? 0.5 : idx / (points.length - 1)));
    const y = top + ((maxY - Number(p[key])) / (maxY - minY)) * usableH;
    return { x, y };
  });

  const p5 = toCoords('lower');
  const p95 = toCoords('upper');
  const mid = toCoords('mid');
  const hoverPoint = hoveredIndex !== null ? mid[hoveredIndex] : null;
  const hoverData = hoveredIndex !== null ? points[hoveredIndex] : null;

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-4 md:p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Cost Forecast (%)</h3>
      <div className="w-full overflow-x-auto">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full min-w-[760px]">
          {[0, 1, 2, 3, 4].map((t) => {
            const y = top + (usableH * t) / 4;
            return <line key={`g-${t}`} x1={left} y1={y} x2={width - right} y2={y} stroke="#E5E7EB" strokeWidth="1" />;
          })}
          <line x1={left} y1={top + usableH} x2={width - right} y2={top + usableH} stroke="#9CA3AF" strokeWidth="1.2" />
          <line x1={left} y1={top} x2={left} y2={top + usableH} stroke="#9CA3AF" strokeWidth="1.2" />

          <path d={buildSmoothPath(p95)} fill="none" stroke="#8FA2C2" strokeWidth="2" />
          <path d={buildSmoothPath(mid)} fill="none" stroke="#F97316" strokeWidth="2.75" />
          <path d={buildSmoothPath(p5)} fill="none" stroke="#8FA2C2" strokeWidth="2" />

          {hoverPoint ? (
            <line
              x1={hoverPoint.x}
              y1={top}
              x2={hoverPoint.x}
              y2={top + usableH}
              stroke="#D1D5DB"
              strokeWidth="1"
            />
          ) : null}

          {points.map((point, idx) => (
            <g key={`${point.label}-${idx}`} onMouseEnter={() => setHoveredIndex(idx)} onMouseLeave={() => setHoveredIndex(null)}>
              <circle cx={p95[idx].x} cy={p95[idx].y} r="3.5" fill="#8FA2C2" />
              <circle cx={mid[idx].x} cy={mid[idx].y} r="4.5" fill="#F97316" />
              <circle cx={p5[idx].x} cy={p5[idx].y} r="3.5" fill="#8FA2C2" />
              <circle cx={mid[idx].x} cy={mid[idx].y} r="11" fill="transparent" />
            </g>
          ))}

          <text x={left - 8} y={top + 4} textAnchor="end" className="fill-gray-500 text-[11px]">{maxY.toFixed(2)}%</text>
          <text x={left - 8} y={top + usableH + 4} textAnchor="end" className="fill-gray-500 text-[11px]">{minY.toFixed(2)}%</text>

          {points.map((point, idx) => (
            <text key={`x-${point.label}-${idx}`} x={mid[idx].x} y={height - 12} textAnchor="middle" className="fill-gray-500 text-[11px]">
              {point.label}
            </text>
          ))}

          {hoverPoint && hoverData ? (
            <foreignObject
              x={Math.min(width - 210, hoverPoint.x + 12)}
              y={Math.max(12, hoverPoint.y - 70)}
              width="198"
              height="92"
            >
              <div className="bg-white/95 border border-gray-300 rounded shadow px-3 py-2 text-xs leading-5">
                <div className="text-gray-700 mb-1 font-medium">{hoverData.label}</div>
                <div className="text-[#8FA2C2]">5th Percentile : {Number(hoverData.lower).toFixed(2)}%</div>
                <div className="text-[#8FA2C2]">95th Percentile : {Number(hoverData.upper).toFixed(2)}%</div>
                <div className="text-[#F97316]">Median : {Number(hoverData.mid).toFixed(2)}%</div>
              </div>
            </foreignObject>
          ) : null}
        </svg>
      </div>
    </div>
  );
};

const ProbabilityMiniChart = ({
  points,
  title = 'Probability of Profitability',
  yLabel = 'Probability (%)',
  xLabel = 'Rate (%)',
  valueFormatter = (v) => `${Number(v).toFixed(0)}%`,
  fixedPercentScale = true,
  yMinOverride = null,
  yMaxOverride = null,
  markerX = null,
  markerLabel = null,
}) => {
  const chartPoints = Array.isArray(points) ? points : [];
  if (!chartPoints.length) {
    return (
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-3">{title}</h3>
        <p className="text-sm text-gray-500">No probability data available yet.</p>
      </div>
    );
  }

  const width = 560;
  const height = 260;
  const left = 46;
  const right = 18;
  const top = 18;
  const bottom = 36;
  const usableW = width - left - right;
  const usableH = height - top - bottom;

  const minX = Math.min(...chartPoints.map((p) => Number(p.x)));
  const maxX = Math.max(...chartPoints.map((p) => Number(p.x)));
  let minY = 0;
  let maxY = 100;
  if (Number.isFinite(yMinOverride) && Number.isFinite(yMaxOverride) && yMaxOverride > yMinOverride) {
    minY = Number(yMinOverride);
    maxY = Number(yMaxOverride);
  }
  if (!fixedPercentScale && !(Number.isFinite(yMinOverride) && Number.isFinite(yMaxOverride) && yMaxOverride > yMinOverride)) {
    const ys = chartPoints.map((p) => Number(p.y)).filter(Number.isFinite);
    if (ys.length > 0) {
      minY = Math.min(...ys);
      maxY = Math.max(...ys);
      if (minY === maxY) {
        const pad = Math.max(Math.abs(minY) * 0.1, 0.2);
        minY -= pad;
        maxY += pad;
      } else {
        const span = maxY - minY;
        const pad = Math.max(span * 0.15, 0.2);
        minY -= pad;
        maxY += pad;
      }
    }
  }

  const coords = chartPoints.map((p, idx) => {
    const x = left + (usableW * (chartPoints.length === 1 ? 0.5 : (Number(p.x) - minX) / ((maxX - minX) || 1)));
    const y = top + ((maxY - Number(p.y)) / (maxY - minY)) * usableH;
    return { x, y, label: p.label, value: p.y };
  });

  const xTicks = (() => {
    const span = Math.max(0.0001, maxX - minX);
    const targetTicks = 8;
    const rawStep = span / targetTicks;
    const niceSteps = [0.1, 0.2, 0.25, 0.5, 1, 2];
    const step = niceSteps.find((s) => s >= rawStep) || 2;

    const start = Math.floor(minX / step) * step;
    const end = Math.ceil(maxX / step) * step;
    const ticks = [];
    for (let v = start; v <= end + 1e-9; v += step) {
      if (v >= minX - 1e-9 && v <= maxX + 1e-9) {
        const rounded = Number(v.toFixed(4));
        const x = left + (usableW * ((rounded - minX) / (span || 1)));
        ticks.push({ value: rounded, x });
      }
    }
    return ticks;
  })();

  // Compute SVG y-coordinates for 0% and 100% to clamp the spline
  const yAtMax = top;                              // 100% → top of chart (SVG y)
  const yAtMin = top + usableH;                    // 0%  → bottom of chart (SVG y)
  const path = buildSmoothPath(coords, yAtMin, yAtMax);

  const markerCoord = (() => {
    if (!Number.isFinite(markerX)) return null;
    if (markerX < minX || markerX > maxX) return null;
    const x = left + (usableW * (chartPoints.length === 1 ? 0.5 : (Number(markerX) - minX) / ((maxX - minX) || 1)));
    return { x };
  })();

  const markerLabelMeta = (() => {
    if (!markerCoord || !markerLabel) return null;
    if (markerCoord.x > (width - right - 56)) {
      return { x: markerCoord.x - 8, anchor: 'end' };
    }
    if (markerCoord.x < (left + 56)) {
      return { x: markerCoord.x + 8, anchor: 'start' };
    }
    return { x: markerCoord.x, anchor: 'middle' };
  })();

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-4 md:p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">{title}</h3>
      <div className="w-full overflow-x-auto">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full min-w-[500px]">
          {[0, 1, 2, 3, 4].map((t) => {
            const y = top + (usableH * t) / 4;
            return <line key={`pg-${t}`} x1={left} y1={y} x2={width - right} y2={y} stroke="#E5E7EB" strokeWidth="1" />;
          })}
          <line x1={left} y1={top + usableH} x2={width - right} y2={top + usableH} stroke="#9CA3AF" strokeWidth="1.2" />
          <line x1={left} y1={top} x2={left} y2={top + usableH} stroke="#9CA3AF" strokeWidth="1.2" />

          {markerCoord ? (
            <line
              x1={markerCoord.x}
              y1={top}
              x2={markerCoord.x}
              y2={top + usableH}
              stroke="#0F766E"
              strokeWidth="1.5"
              strokeDasharray="6 4"
            />
          ) : null}

          <path d={path} fill="none" stroke="#F97316" strokeWidth="2.75" />
          {coords.map((c) => (
            <circle key={`p-${c.label}`} cx={c.x} cy={c.y} r="4" fill="#F97316" />
          ))}

          {markerCoord && markerLabel && markerLabelMeta ? (
            <text x={markerLabelMeta.x} y={top - 4} textAnchor={markerLabelMeta.anchor} className="fill-teal-700 text-[11px] font-medium">
              {markerLabel}
            </text>
          ) : null}

          <text x={left - 8} y={top + 4} textAnchor="end" className="fill-gray-500 text-[11px]">{valueFormatter(maxY)}</text>
          <text x={left - 8} y={top + usableH + 4} textAnchor="end" className="fill-gray-500 text-[11px]">{valueFormatter(minY)}</text>

          {xTicks.map((tick) => (
            <text key={`xt-${tick.value}`} x={tick.x} y={height - 12} textAnchor="middle" className="fill-gray-500 text-[11px]">
              {Number(tick.value).toFixed(2).replace(/\.00$/, '').replace(/(\.\d)0$/, '$1')}
            </text>
          ))}

          {xLabel ? (
            <text x={left + (usableW / 2)} y={height - 1} textAnchor="middle" className="fill-gray-500 text-[12px] font-medium">
              {xLabel}
            </text>
          ) : null}

          <text x="20" y={top + usableH / 2} textAnchor="middle" transform={`rotate(-90 20 ${top + usableH / 2})`} className="fill-gray-400 text-[11px]">
            {yLabel}
          </text>
        </svg>
      </div>
    </div>
  );
};

const ResultsPanel = ({ results, hasCurrentRate, onNewCalculation }) => {
  const [showMoreDetails, setShowMoreDetails] = useState(false);

  if (!results) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex items-center justify-center h-full min-h-[400px] text-gray-400">
          <p>Submit the form to see results</p>
        </div>
      </div>
    );
  }

  const hasEstimatedProfitRange =
    results?.estimatedProfitMin !== null && results?.estimatedProfitMin !== undefined &&
    results?.estimatedProfitMax !== null && results?.estimatedProfitMax !== undefined;

  const getAmountClass = (value) => (Number(value) < 0 ? 'text-red-600' : 'text-[#17a455]');

  const getOrderedProfitRange = () => {
    if (!hasEstimatedProfitRange) {
      return null;
    }

    const first = Number(results.estimatedProfitMin);
    const second = Number(results.estimatedProfitMax);
    if (Number.isNaN(first) || Number.isNaN(second)) {
      return null;
    }

    return first <= second ? { low: first, high: second } : { low: second, high: first };
  };

  const orderedProfitRange = getOrderedProfitRange();

  // Map backend profitability curve directly to chart points.
  // The backend already returns a correctly shaped S-curve with proper
  // probability values — no additional smoothing / capping / zeroing needed.
  // Enforce monotonicity client-side as a safety net (probability must be
  // non-decreasing as rate increases, and must never cross 0% or 100% twice).
  const directCurvePoints = (() => {
    if (!Array.isArray(results?.profitabilityCurve) || results.profitabilityCurve.length === 0) {
      return [];
    }
    const raw = results.profitabilityCurve
      .map((point) => ({
        x: Number(point?.rate_pct),
        y: Math.max(0, Math.min(100, Number(point?.probability_pct || 0))),
        label: String(point?.rate_pct),
      }))
      .filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y))
      .sort((a, b) => a.x - b.x);

    // Enforce monotonicity: each point's y must be >= the previous
    for (let i = 1; i < raw.length; i += 1) {
      if (raw[i].y < raw[i - 1].y) {
        raw[i].y = raw[i - 1].y;
      }
    }
    return raw;
  })();

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header with New Calculation Button */}
        {onNewCalculation && (
          <div className="mb-8 flex items-center justify-between">
            <button 
              onClick={onNewCalculation}
              className="flex items-center gap-2 text-gray-600 hover:text-gray-900 transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
              <span className="font-medium">New Calculation</span>
            </button>
            <h1 className="text-2xl font-semibold text-gray-900 flex-1 text-center">Profitability Calculation Results</h1>
            <div className="w-[140px]"></div>
          </div>
        )}

        {hasCurrentRate ? (
          // Layout when current rate is entered
          <div className="space-y-6">
            {/* Blue box with profitability metrics */}
            <div className="bg-blue-50 rounded-2xl p-6 border border-blue-100 shadow-sm">
              <div className="space-y-3">
                <div>
                  <p className="text-sm font-medium text-gray-700">% of profitability:</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {results.profitability !== null && results.profitability !== undefined 
                      ? `${results.profitability}%` 
                      : 'Pending backend calculation'}
                  </p>
                </div>
                
                <div>
                  <p className="text-sm font-medium text-gray-700">Margin (in bps):</p>
                  <p className={`text-2xl font-bold ${Number(results.margin || 0) < 0 ? 'text-red-600' : 'text-gray-900'}`}>
                    {results.margin !== null && results.margin !== undefined 
                      ? results.margin 
                      : 'Pending backend calculation'}
                  </p>
                </div>
                
                <div>
                  <p className="text-sm font-medium text-gray-700">Estimated Profit:</p>
                  {orderedProfitRange ? (
                    <p className="text-3xl font-bold">
                      <span className={getAmountClass(orderedProfitRange.low)}>
                        {formatCurrency(orderedProfitRange.low)}
                      </span>
                      <span className="text-gray-900"> - </span>
                      <span className={getAmountClass(orderedProfitRange.high)}>{formatCurrency(orderedProfitRange.high)}</span>
                    </p>
                  ) : (
                    <p className={`text-2xl font-bold ${Number(results.estimatedProfit || 0) < 0 ? 'text-red-600' : 'text-[#17a455]'}`}>
                      {results.estimatedProfit !== null && results.estimatedProfit !== undefined
                        ? formatCurrency(results.estimatedProfit)
                        : 'Pending backend calculation'}
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* Current Rate (or Suggested Rate when no current rate entered) */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
              <p className="text-sm font-medium text-gray-700 mb-2">Current Rate:</p>
              <p className="text-4xl font-bold text-gray-900">
                {results.suggestedRate !== null && results.suggestedRate !== undefined
                  ? `${Number(results.suggestedRate).toFixed(2)}%`
                  : 'Pending backend calculation'}
              </p>
            </div>

            {/* More Details Button */}
            <Button
              onClick={() => setShowMoreDetails(!showMoreDetails)}
              className="w-full"
            >
              {showMoreDetails ? 'Show Less' : 'More Details'}
            </Button>

            {/* Additional Details Section */}
            {showMoreDetails && (
              <>
                <SarimaMiniChart
                  series={
                    Array.isArray(results.costForecast) && results.costForecast.length > 0
                      ? results.costForecast.map((p) => ({
                          label: p.label || `Month ${p.month_index || ''}`,
                          mid: Number(p.mid || 0) * 100,
                          lower: Number(p.lower || 0) * 100,
                          upper: Number(p.upper || 0) * 100,
                        }))
                      : buildFallbackCostSeries(results.suggestedRate)
                  }
                />

                {/* Profitability curve from ML forecasting */}
                {Array.isArray(results.profitabilityCurve) && results.profitabilityCurve.length > 0 && (
                  <ProbabilityMiniChart
                    title="Probability of Profitability"
                    yLabel="Probability (%)"
                    xLabel="Rate (%)"
                    valueFormatter={(v) => `${Number(v).toFixed(2)}%`}
                    fixedPercentScale
                    yMinOverride={0}
                    yMaxOverride={100}
                    markerX={Number.isFinite(Number(results.suggestedRate)) ? Number(results.suggestedRate) : null}
                    markerLabel={
                      Number.isFinite(Number(results.suggestedRate))
                        ? `Current Rate ${Number(results.suggestedRate).toFixed(2)}%`
                        : null
                    }
                    points={directCurvePoints}
                  />
                )}

                <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 space-y-4">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Additional Details</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <p className="text-sm text-gray-600">Average Transaction Size</p>
                      <p className="text-2xl font-bold text-gray-900">
                        ${results.averageTransactionSize?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-600">Expected Annual Volume</p>
                      <p className="text-2xl font-bold text-gray-900">
                        {(() => {
                          const monthlyVolume = Number(results.processingVolume || results.expectedVolume || 0);
                          if (!monthlyVolume) return '$0 - $0';
                          const annual = monthlyVolume * 12;
                          const lower = annual * 0.75;
                          const upper = annual * 1.25;
                          return `${formatCurrency(lower)} - ${formatCurrency(upper)}`;
                        })()}
                      </p>
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        ) : (
          // Layout when no current rate
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left Column */}
            <div className="space-y-6">
              {/* Suggested Rate */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
                <p className="text-sm font-medium text-gray-700 mb-2">Suggested Rate:</p>
                <p className="text-4xl font-bold text-[#17a455]">
                  {results.suggestedRate !== null && results.suggestedRate !== undefined ? `${Number(results.suggestedRate).toFixed(2)}%` : 'Pending backend calculation'}
                </p>
              </div>

              <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
                <p className="text-sm font-medium text-gray-700 mb-2">Margin (in bps):</p>
                <p className={`text-4xl font-bold ${Number(results.margin || 0) < 0 ? 'text-red-600' : 'text-gray-900'}`}>
                  {results.margin !== null && results.margin !== undefined ? results.margin : 'Pending backend calculation'}
                </p>
              </div>

              <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
                <p className="text-sm font-medium text-gray-700 mb-2">Estimated Profit:</p>
                {orderedProfitRange ? (
                  <p className="text-4xl font-bold">
                    <span className={getAmountClass(orderedProfitRange.low)}>
                      {formatCurrency(orderedProfitRange.low)}
                    </span>
                    <span className="text-gray-900"> - </span>
                    <span className={getAmountClass(orderedProfitRange.high)}>{formatCurrency(orderedProfitRange.high)}</span>
                  </p>
                ) : (
                  <p className={`text-4xl font-bold ${Number(results.estimatedProfit || 0) < 0 ? 'text-red-600' : 'text-[#17a455]'}`}>
                    {results.estimatedProfit !== null && results.estimatedProfit !== undefined
                      ? formatCurrency(results.estimatedProfit)
                      : 'Pending backend calculation'}
                  </p>
                )}
              </div>

              <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
                <p className="text-sm font-medium text-gray-700 mb-2">Expected Annual Volume:</p>
                <p className="text-4xl font-bold text-gray-900">
                  {(() => {
                    const monthlyVolume = Number(results.processingVolume || results.expectedVolume || 0);
                    if (!monthlyVolume) return '$0 - $0';
                    const annual = monthlyVolume * 12;
                    const lower = annual * 0.75;
                    const upper = annual * 1.25;
                    return `${formatCurrency(lower)} - ${formatCurrency(upper)}`;
                  })()}
                </p>
              </div>
            </div>

            {/* Right Column */}
            <div className="space-y-6">
              <ProbabilityMiniChart
                title="Probability of Profitability"
                yLabel="Probability (%)"
                xLabel="Rate (%)"
                valueFormatter={(v) => `${Number(v).toFixed(2)}%`}
                fixedPercentScale
                yMinOverride={0}
                yMaxOverride={100}
                markerX={Number.isFinite(Number(results.suggestedRate)) ? Number(results.suggestedRate) : null}
                markerLabel={
                  Number.isFinite(Number(results.suggestedRate))
                    ? `Suggested ${Number(results.suggestedRate).toFixed(2)}%`
                    : null
                }
                points={directCurvePoints}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ResultsPanel;
