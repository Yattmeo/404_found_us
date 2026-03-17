import React, { useMemo, useState } from 'react';
import { ArrowLeft, ChevronDown, ChevronUp } from 'lucide-react';

const DesiredMarginResults = ({ results, onNewCalculation }) => {
  const [showDetails, setShowDetails] = useState(false);

  if (!results) {
    return null;
  }

  const formatCurrency = (value) => {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
      return null;
    }
    const amount = Number(value);
    const absFormatted = Math.abs(amount).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return amount < 0 ? `-$${absFormatted}` : `$${absFormatted}`;
  };

  const formatCurrencyRange = (low, high) => {
    if (
      low === null || low === undefined || Number.isNaN(Number(low)) ||
      high === null || high === undefined || Number.isNaN(Number(high))
    ) {
      return null;
    }
    return `${formatCurrency(low)} - ${formatCurrency(high)}`;
  };

  const formatMonthYear = (dateObj) => dateObj.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
  const formatMonthShort = (dateObj) => dateObj.toLocaleDateString('en-US', { month: 'short' });

  const getWeekOfMonth = (dateObj) => Math.floor((dateObj.getDate() - 1) / 7) + 1;

  const extractDateFromPoint = (point, index) => {
    const label = String(point?.label || '');
    const dateInParen = label.match(/\((\d{4}-\d{2}-\d{2})\)/);
    if (dateInParen) {
      return new Date(`${dateInParen[1]}T00:00:00`);
    }

    const fallbackWeek = Number(point?.week_index) || index + 1;
    const now = new Date();
    const fallback = new Date(now);
    fallback.setDate(now.getDate() + (fallbackWeek - 1) * 7);
    return fallback;
  };

  const toWeeklyCostSeries = (series) => (Array.isArray(series) ? series : []).map((point, index) => {
    const date = extractDateFromPoint(point, index);
    return {
      date,
      label: `W${getWeekOfMonth(date)}-${formatMonthShort(date)}`,
      p5: Number(point.lower || 0) * 100,
      p95: Number(point.upper || 0) * 100,
      median: Number(point.mid || 0) * 100,
    };
  });

  const toWeeklyVolumeSeries = (series) => (Array.isArray(series) ? series : []).map((point, index) => {
    const date = extractDateFromPoint(point, index);
    return {
      date,
      label: `W${getWeekOfMonth(date)}-${formatMonthShort(date)}`,
      value: Number(point.mid || 0),
    };
  });

  const buildYearCaption = (dates, fallbackStart, fallbackEnd) => {
    const validDates = (dates || []).filter((d) => d instanceof Date && !Number.isNaN(d.getTime()));
    if (validDates.length) {
      const years = validDates.map((d) => d.getFullYear());
      const minYear = Math.min(...years);
      const maxYear = Math.max(...years);
      return minYear === maxYear ? `${minYear}` : `${minYear}-${maxYear}`;
    }

    const start = fallbackStart ? new Date(`${fallbackStart}T00:00:00`) : null;
    const end = fallbackEnd ? new Date(`${fallbackEnd}T00:00:00`) : null;
    if (start && end && !Number.isNaN(start.getTime()) && !Number.isNaN(end.getTime())) {
      const startYear = start.getFullYear();
      const endYear = end.getFullYear();
      return startYear === endYear ? `${startYear}` : `${startYear}-${endYear}`;
    }

    return '';
  };

  const buildSmoothPath = (coords) => {
    if (coords.length === 0) {
      return '';
    }
    if (coords.length === 1) {
      return `M ${coords[0].x} ${coords[0].y}`;
    }

    let path = `M ${coords[0].x} ${coords[0].y}`;
    for (let i = 0; i < coords.length - 1; i += 1) {
      const p0 = coords[i - 1] || coords[i];
      const p1 = coords[i];
      const p2 = coords[i + 1];
      const p3 = coords[i + 2] || p2;

      const cp1x = p1.x + (p2.x - p0.x) / 6;
      const cp1y = p1.y + (p2.y - p0.y) / 6;
      const cp2x = p2.x - (p3.x - p1.x) / 6;
      const cp2y = p2.y - (p3.y - p1.y) / 6;
      path += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x} ${p2.y}`;
    }
    return path;
  };

  const SarimaChart = ({ points, yearCaption = '' }) => {
    const [hoveredIndex, setHoveredIndex] = useState(null);
    const chartPoints = Array.isArray(points) ? points : [];

    const state = useMemo(() => {
      if (!chartPoints.length) {
        return null;
      }

      const width = 900;
      const height = 300;
      const left = 52;
      const right = 22;
      const top = 18;
      const bottom = 40;
      const usableW = width - left - right;
      const usableH = height - top - bottom;

      const allValues = chartPoints.flatMap((p) => [p.p5, p.p95, p.median]).filter((v) => Number.isFinite(v));
      let minY = Math.min(...allValues);
      let maxY = Math.max(...allValues);
      if (minY === maxY) {
        minY -= 0.1;
        maxY += 0.1;
      }

      const toCoords = (key) => chartPoints.map((point, index) => {
        const x = left + (usableW * (chartPoints.length === 1 ? 0.5 : index / (chartPoints.length - 1)));
        const y = top + ((maxY - point[key]) / (maxY - minY)) * usableH;
        return { x, y };
      });

      return {
        width,
        height,
        left,
        right,
        top,
        bottom,
        usableW,
        usableH,
        minY,
        maxY,
        p5Coords: toCoords('p5'),
        p95Coords: toCoords('p95'),
        medianCoords: toCoords('median'),
      };
    }, [chartPoints]);

    if (!state) {
      return (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">SARIMA Forecast - Cost (%)</h3>
          <p className="text-sm text-gray-500">No chart data available yet.</p>
        </div>
      );
    }

    const {
      width,
      height,
      left,
      right,
      top,
      usableH,
      p5Coords,
      p95Coords,
      medianCoords,
      minY,
      maxY,
    } = state;

    const hoverPoint = hoveredIndex !== null ? medianCoords[hoveredIndex] : null;
    const hoverData = hoveredIndex !== null ? chartPoints[hoveredIndex] : null;

    return (
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-4 md:p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">SARIMA Forecast - Cost (%)</h3>
        <div className="w-full overflow-x-auto">
          <svg viewBox={`0 0 ${width} ${height}`} className="w-full min-w-[760px]" role="img" aria-label="SARIMA cost chart">
            {[0, 1, 2, 3, 4].map((tick) => {
              const y = top + (usableH * tick) / 4;
              return <line key={`grid-${tick}`} x1={left} y1={y} x2={width - right} y2={y} stroke="#E5E7EB" strokeWidth="1" />;
            })}

            <line x1={left} y1={top + usableH} x2={width - right} y2={top + usableH} stroke="#9CA3AF" strokeWidth="1.2" />
            <line x1={left} y1={top} x2={left} y2={top + usableH} stroke="#9CA3AF" strokeWidth="1.2" />

            <path d={buildSmoothPath(p5Coords)} fill="none" stroke="#8FA2C2" strokeWidth="2" />
            <path d={buildSmoothPath(p95Coords)} fill="none" stroke="#8FA2C2" strokeWidth="2" />
            <path d={buildSmoothPath(medianCoords)} fill="none" stroke="#F97316" strokeWidth="2.75" />

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

            {chartPoints.map((point, index) => (
              <g key={`pts-${point.label}-${index}`} onMouseEnter={() => setHoveredIndex(index)} onMouseLeave={() => setHoveredIndex(null)}>
                <circle cx={p5Coords[index].x} cy={p5Coords[index].y} r="4" fill="#8FA2C2" />
                <circle cx={p95Coords[index].x} cy={p95Coords[index].y} r="4" fill="#8FA2C2" />
                <circle cx={medianCoords[index].x} cy={medianCoords[index].y} r="5" fill="#F97316" stroke="#fff" strokeWidth="1.5" />
                <circle cx={medianCoords[index].x} cy={medianCoords[index].y} r="10" fill="transparent" />
              </g>
            ))}

            <text x={left - 8} y={top + 4} textAnchor="end" className="fill-gray-500 text-[11px]">{maxY.toFixed(2)}%</text>
            <text x={left - 8} y={top + usableH + 4} textAnchor="end" className="fill-gray-500 text-[11px]">{minY.toFixed(2)}%</text>

            {chartPoints.map((point, index) => (
              <text key={`x-${point.label}-${index}`} x={medianCoords[index].x} y={height - 12} textAnchor="middle" className="fill-gray-500 text-[11px]">
                {point.label}
              </text>
            ))}

            {yearCaption ? (
              <text x={left + state.usableW / 2} y={height - 1} textAnchor="middle" className="fill-gray-400 text-[11px]">
                {yearCaption}
              </text>
            ) : null}

            <text x="20" y={top + usableH / 2} textAnchor="middle" transform={`rotate(-90 20 ${top + usableH / 2})`} className="fill-gray-400 text-[11px]">Cost (%)</text>

            {hoverPoint && hoverData ? (
              <foreignObject
                x={Math.min(width - 200, hoverPoint.x + 14)}
                y={Math.max(16, hoverPoint.y - 70)}
                width="188"
                height="94"
              >
                <div className="bg-white/95 border border-gray-300 rounded shadow px-3 py-2 text-xs leading-5">
                  <div className="text-gray-700 mb-1 font-medium">{hoverData.label}</div>
                  <div className="text-[#8FA2C2]">5th Percentile : {hoverData.p5.toFixed(2)}%</div>
                  <div className="text-[#8FA2C2]">95th Percentile : {hoverData.p95.toFixed(2)}%</div>
                  <div className="text-[#F97316]">Median : {hoverData.median.toFixed(2)}%</div>
                </div>
              </foreignObject>
            ) : null}
          </svg>
        </div>
      </div>
    );
  };

  const SingleCurveChart = ({ title, points, yLabel, valueFormatter, useSmooth = true, tooltipLabel = 'Value', yearCaption = '' }) => {
    const [hoveredIndex, setHoveredIndex] = useState(null);
    const chartPoints = Array.isArray(points) ? points : [];

    const state = useMemo(() => {
      if (!chartPoints.length) {
        return null;
      }
      const width = 900;
      const height = 300;
      const left = 52;
      const right = 22;
      const top = 18;
      const bottom = 40;
      const usableW = width - left - right;
      const usableH = height - top - bottom;

      const ys = chartPoints.map((p) => Number(p.value || 0));
      let minY = Math.min(...ys);
      let maxY = Math.max(...ys);
      if (minY === maxY) {
        const pad = Math.max(Math.abs(minY) * 0.05, 1);
        minY -= pad;
        maxY += pad;
      }

      const coords = chartPoints.map((point, index) => {
        const x = left + (usableW * (chartPoints.length === 1 ? 0.5 : index / (chartPoints.length - 1)));
        const y = top + ((maxY - point.value) / (maxY - minY)) * usableH;
        return { x, y };
      });

      return { width, height, left, right, top, bottom, usableW, usableH, minY, maxY, coords };
    }, [chartPoints]);

    if (!state) {
      return (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">{title}</h3>
          <p className="text-sm text-gray-500">No chart data available yet.</p>
        </div>
      );
    }

    const { width, height, left, right, top, usableH, minY, maxY, coords } = state;
    const hoverPoint = hoveredIndex !== null ? coords[hoveredIndex] : null;
    const hoverData = hoveredIndex !== null ? chartPoints[hoveredIndex] : null;

    const straightPath = coords.length
      ? `M ${coords.map((c) => `${c.x} ${c.y}`).join(' L ')}`
      : '';

    return (
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-4 md:p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">{title}</h3>
        <div className="w-full overflow-x-auto">
          <svg viewBox={`0 0 ${width} ${height}`} className="w-full min-w-[760px]" role="img" aria-label={title}>
            {[0, 1, 2, 3, 4].map((tick) => {
              const y = top + (usableH * tick) / 4;
              return <line key={`grid-${tick}`} x1={left} y1={y} x2={width - right} y2={y} stroke="#E5E7EB" strokeWidth="1" />;
            })}
            <line x1={left} y1={top + usableH} x2={width - right} y2={top + usableH} stroke="#9CA3AF" strokeWidth="1.2" />
            <line x1={left} y1={top} x2={left} y2={top + usableH} stroke="#9CA3AF" strokeWidth="1.2" />

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

            <path d={useSmooth ? buildSmoothPath(coords) : straightPath} fill="none" stroke="#F97316" strokeWidth="3" />
            {coords.map((c, idx) => (
              <g key={`dot-${idx}`} onMouseEnter={() => setHoveredIndex(idx)} onMouseLeave={() => setHoveredIndex(null)}>
                <circle cx={c.x} cy={c.y} r="4.5" fill="#F97316" />
                <circle cx={c.x} cy={c.y} r="10" fill="transparent" />
              </g>
            ))}

            <text x={left - 8} y={top + 4} textAnchor="end" className="fill-gray-500 text-[11px]">{valueFormatter(maxY)}</text>
            <text x={left - 8} y={top + usableH + 4} textAnchor="end" className="fill-gray-500 text-[11px]">{valueFormatter(minY)}</text>

            {chartPoints.map((point, index) => (
              <text key={`x-${point.label}-${index}`} x={coords[index].x} y={height - 12} textAnchor="middle" className="fill-gray-500 text-[11px]">
                {point.label}
              </text>
            ))}

            {yearCaption ? (
              <text x={left + state.usableW / 2} y={height - 1} textAnchor="middle" className="fill-gray-400 text-[11px]">
                {yearCaption}
              </text>
            ) : null}

            <text x="20" y={top + usableH / 2} textAnchor="middle" transform={`rotate(-90 20 ${top + usableH / 2})`} className="fill-gray-400 text-[11px]">{yLabel}</text>

            {hoverPoint && hoverData ? (
              <foreignObject
                x={Math.min(width - 196, hoverPoint.x + 14)}
                y={Math.max(16, hoverPoint.y - 48)}
                width="188"
                height="64"
              >
                <div className="bg-white/95 border border-gray-300 rounded shadow px-3 py-2 text-xs leading-5">
                  <div className="text-gray-700 mb-1 font-medium">{hoverData.label}</div>
                  <div className="text-[#F97316]">{tooltipLabel}: {valueFormatter(hoverData.value)}</div>
                </div>
              </foreignObject>
            ) : null}
          </svg>
        </div>
      </div>
    );
  };

  const suggestedRate = results.suggestedRate;
  const marginBps = results.marginBps;
  const isEstimatedProfitNegative = Number(results.estimatedProfitMin || 0) < 0;
  const estimatedProfitRange = formatCurrencyRange(results.estimatedProfitMin, results.estimatedProfitMax);

  const costSeries = toWeeklyCostSeries(results.costForecast || []);

  const volumeSeries = toWeeklyVolumeSeries(results.volumeForecast || []);

  const profitabilitySeries = (results.profitabilityCurve || []).map((point) => ({
    label: `${point.rate_pct}`,
    value: Number(point.probability_pct || 0),
  }));

  const transactionSummary = results.transactionSummary || null;
  const timeAxisCaption = buildYearCaption(
    [...costSeries.map((p) => p.date), ...volumeSeries.map((p) => p.date)],
    transactionSummary?.start_date,
    transactionSummary?.end_date,
  );
  const summaryMerchantId =
    results.transactionSummary?.merchant_id ||
    results.parsedData?.merchantId ||
    'N/A';

  return (
    <div className="min-h-screen bg-[#d7e5e2] p-6 md:p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8 flex items-center justify-between">
          <button 
            onClick={onNewCalculation}
            className="flex items-center gap-2 text-gray-600 hover:text-gray-900 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
            <span className="font-medium">New Calculation</span>
          </button>
          <h1 className="text-2xl font-semibold text-gray-900 flex-1 text-center">Rates Quotation Results</h1>
          <div className="w-[140px]"></div>
        </div>

        <div className="space-y-5">
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
            <p className="text-sm font-medium text-gray-700 mb-2">Suggested Rate:</p>
            <p className="text-4xl font-bold text-[#17a455]">
              {suggestedRate !== null && suggestedRate !== undefined
                ? `${Number(suggestedRate).toFixed(2)}%`
                : <span className="text-xl text-gray-400">Pending backend calculation</span>}
            </p>
          </div>

          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
            <p className="text-sm font-medium text-gray-700 mb-2">Margin (in bps):</p>
            <p className="text-4xl font-bold text-gray-900">
              {marginBps !== null && marginBps !== undefined
                ? `${marginBps}`
                : <span className="text-xl text-gray-400">Pending backend calculation</span>}
            </p>
          </div>

          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
            <p className="text-sm font-medium text-gray-700 mb-2">Estimated Profit:</p>
            <p className={`text-4xl font-bold ${isEstimatedProfitNegative ? 'text-red-600' : 'text-[#17a455]'}`}>
              {estimatedProfitRange
                ? estimatedProfitRange
                : <span className="text-xl text-gray-400">Pending backend calculation</span>}
            </p>
          </div>

          <button
            type="button"
            onClick={() => setShowDetails((prev) => !prev)}
            className="w-full bg-[#22C55E] hover:bg-[#16A34A] text-white font-semibold py-3 px-4 rounded-2xl transition-colors flex items-center justify-center gap-2"
          >
            More Details
            {showDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>

          {showDetails && (
            <div className="space-y-6 pt-2">
              <SarimaChart points={costSeries} yearCaption={timeAxisCaption} />

              <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Transaction Summary</h3>
                {transactionSummary ? (
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <div className="text-gray-500 mb-1">Merchant ID</div>
                      <div className="font-semibold text-gray-900">{summaryMerchantId}</div>
                    </div>
                    <div>
                      <div className="text-gray-500 mb-1">MCC Code</div>
                      <div className="font-semibold text-gray-900">{transactionSummary.mcc ?? results.parsedData?.mcc ?? 'N/A'}</div>
                    </div>
                    <div>
                      <div className="text-gray-500 mb-1">Total Transactions</div>
                      <div className="font-semibold text-gray-900">{Number(transactionSummary.transaction_count || 0).toLocaleString('en-US')}</div>
                    </div>
                    <div>
                      <div className="text-gray-500 mb-1">Average Ticket</div>
                      <div className="font-semibold text-gray-900">{formatCurrency(transactionSummary.average_ticket) || 'N/A'}</div>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">Transaction summary is not available.</p>
                )}
              </div>

              <SingleCurveChart
                title="Volume Trend ($)"
                points={volumeSeries}
                yLabel="Volume ($)"
                valueFormatter={(v) => `${Math.round(v).toLocaleString('en-US')}`}
                useSmooth={false}
                tooltipLabel="Value"
                yearCaption={timeAxisCaption}
              />

              <SingleCurveChart
                title="Probability of Profitability"
                points={profitabilitySeries}
                yLabel="Probability (%)"
                valueFormatter={(v) => `${Number(v).toFixed(0)}%`}
                useSmooth={true}
                tooltipLabel="Probability"
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DesiredMarginResults;
