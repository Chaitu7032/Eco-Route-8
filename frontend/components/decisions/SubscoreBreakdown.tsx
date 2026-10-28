"use client";

import { CandidateRanking, SchedulingWeights } from "@/lib/types";
import { formatEmissions } from "@/lib/utils";

interface SubscoreBreakdownProps {
  candidates?: CandidateRanking[];
  weights?: SchedulingWeights | null;
}

export function SubscoreBreakdown({ candidates = [], weights }: SubscoreBreakdownProps) {
  const safeWeights = {
    carbon_weight: Number(weights?.carbon_weight ?? 0.4),
    time_weight: Number(weights?.time_weight ?? weights?.cost_weight ?? 0.2),
    utilization_weight: Number(weights?.utilization_weight ?? 0.2),
    latency_weight: Number(weights?.latency_weight ?? 0.2),
  };

  const feasibleCandidates = (candidates || []).filter(
    (c: any) => c.is_feasible ?? (c.rank !== undefined && c.rank > 0 && !c.rejection_reason)
  );

  if (feasibleCandidates.length === 0) {
    return (
      <div className="p-4 text-center text-xs text-slate-400 font-mono">
        No feasible candidate regions available to render subscore decomposition.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Purpose & Mathematical Explanation Banner */}
      <div className="p-4 rounded-xl bg-slate-950/70 border border-slate-800 space-y-2">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-2">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <h5 className="font-bold text-slate-100 font-sans text-xs">
              Multi-Objective Penalty Score Decomposition ($J_r$)
            </h5>
          </div>
          <span className="text-[11px] font-mono text-emerald-400 font-bold">
            Lower Score = Better Candidate (Rank #1 Wins)
          </span>
        </div>
        <p className="text-xs text-slate-300 leading-relaxed font-sans">
          This section breaks down <strong className="text-white">why each region ranked where it did</strong>. The horizontal stacked bar visualizes each factor&apos;s penalty contribution:
          <span className="text-emerald-400 font-mono"> Carbon (40%)</span>,
          <span className="text-blue-400 font-mono"> Execution Duration (30%)</span>,
          <span className="text-purple-400 font-mono"> Host Utilization (20%)</span>, and
          <span className="text-cyan-400 font-mono"> Network Latency (10%)</span>.
          Raw physical units (gCO₂, seconds, %, ms) are normalized to a $[0.0, 1.0]$ scale ($n$) across all candidate regions so they can be mathematically combined.
        </p>
      </div>

      <div className="text-xs text-slate-400 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <span className="font-semibold text-slate-300 font-mono">
          Formula: <span className="text-emerald-400 font-bold">J_r = 0.40·N(Carbon) + 0.30·N(Duration) + 0.20·N(Util) + 0.10·N(Latency)</span>
        </span>
        <div className="flex flex-wrap items-center gap-3 font-mono text-[11px]">
          <span className="flex items-center gap-1 text-emerald-400">
            <span className="w-2 h-2 rounded bg-emerald-500" /> Carbon ({safeWeights.carbon_weight.toFixed(2)})
          </span>
          <span className="flex items-center gap-1 text-blue-400">
            <span className="w-2 h-2 rounded bg-blue-500" /> Duration ({safeWeights.time_weight.toFixed(2)})
          </span>
          <span className="flex items-center gap-1 text-purple-400">
            <span className="w-2 h-2 rounded bg-purple-500" /> Util ({safeWeights.utilization_weight.toFixed(2)})
          </span>
          <span className="flex items-center gap-1 text-cyan-400">
            <span className="w-2 h-2 rounded bg-cyan-500" /> Latency ({safeWeights.latency_weight.toFixed(2)})
          </span>
        </div>
      </div>

      <div className="space-y-3">
        {feasibleCandidates.map((cand: any) => {
          const compScore = cand.composite_score != null ? Number(cand.composite_score) : (cand.cost_score_jr != null ? Number(cand.cost_score_jr) : 0);
          const rawCarbon = cand.raw_carbon_gco2 != null ? Number(cand.raw_carbon_gco2) : (cand.emissions_co2eq != null ? Number(cand.emissions_co2eq) : 0);
          const rawDuration = cand.raw_duration_seconds != null ? Number(cand.raw_duration_seconds) : (cand.estimated_duration != null ? Number(cand.estimated_duration) : 0);
          const rawLatency = cand.raw_latency_ms != null ? Number(cand.raw_latency_ms) : (cand.network_latency_ms != null ? Number(cand.network_latency_ms) : 0);
          const projUtil = cand.projected_utilization != null ? Number(cand.projected_utilization) : (cand.utilization != null ? Number(cand.utilization) : 0);

          const normCarbon = cand.norm_carbon != null ? Number(cand.norm_carbon) : (cand.score_breakdown?.norm_carbon != null ? Number(cand.score_breakdown.norm_carbon) : 0);
          const normDuration = cand.norm_duration != null ? Number(cand.norm_duration) : (cand.score_breakdown?.norm_duration != null ? Number(cand.score_breakdown.norm_duration) : (cand.norm_cost != null ? Number(cand.norm_cost) : 0));
          const normUtil = cand.norm_utilization != null ? Number(cand.norm_utilization) : (cand.score_breakdown?.norm_utilization != null ? Number(cand.score_breakdown.norm_utilization) : 0);
          const normLatency = cand.norm_latency != null ? Number(cand.norm_latency) : (cand.score_breakdown?.norm_latency != null ? Number(cand.score_breakdown.norm_latency) : 0);

          // Subscores
          const carbonPart = Math.max(0, Number(cand.subscore_carbon ?? (cand.score_breakdown?.weighted_carbon ?? 0)));
          const durationPart = Math.max(0, Number(cand.subscore_duration ?? cand.subscore_cost ?? (cand.score_breakdown?.weighted_duration ?? 0)));
          const utilPart = Math.max(0, Number(cand.subscore_utilization ?? (cand.score_breakdown?.weighted_utilization ?? 0)));
          const latencyPart = Math.max(0, Number(cand.subscore_latency ?? (cand.score_breakdown?.weighted_latency ?? 0)));
          
          const totalSub = carbonPart + durationPart + utilPart + latencyPart || 1;

          const carbonPct = (carbonPart / totalSub) * 100;
          const durationPct = (durationPart / totalSub) * 100;
          const utilPct = (utilPart / totalSub) * 100;
          const latencyPct = (latencyPart / totalSub) * 100;

          const isOptimal = cand.rank === 1;

          return (
            <div
              key={cand.region_id || cand.region_code}
              className={`p-3.5 rounded-xl border transition-all ${
                isOptimal
                  ? "bg-emerald-950/20 border-emerald-500/40 shadow-md shadow-emerald-950/30"
                  : "bg-slate-950/60 border-slate-800"
              }`}
            >
              <div className="flex items-center justify-between text-xs mb-2">
                <div className="flex items-center gap-2">
                  <span
                    className={`font-mono px-2 py-0.5 rounded text-[11px] font-bold ${
                      isOptimal
                        ? "bg-emerald-500 text-slate-950"
                        : "bg-slate-800 text-slate-300"
                    }`}
                  >
                    #{cand.rank}
                  </span>
                  <span className="font-bold text-slate-100 font-mono text-sm">
                    {cand.region_code}
                  </span>
                  {isOptimal && (
                    <span className="text-[10px] uppercase font-mono text-emerald-400 bg-emerald-950/80 px-2 py-0.5 rounded border border-emerald-500/40 font-bold">
                      Optimal Target
                    </span>
                  )}
                </div>
                <span className="font-mono text-xs font-bold text-emerald-400">
                  J_r = {compScore.toFixed(4)}
                </span>
              </div>

              {/* Stacked Component Bar */}
              <div className="w-full bg-slate-900 h-2.5 rounded-full overflow-hidden flex border border-slate-800">
                <div
                  className="bg-emerald-500 h-full transition-all duration-300"
                  style={{ width: `${carbonPct}%` }}
                  title={`Carbon: ${carbonPart.toFixed(4)} (${carbonPct.toFixed(1)}%)`}
                />
                <div
                  className="bg-blue-500 h-full transition-all duration-300"
                  style={{ width: `${durationPct}%` }}
                  title={`Duration: ${durationPart.toFixed(4)} (${durationPct.toFixed(1)}%)`}
                />
                <div
                  className="bg-purple-500 h-full transition-all duration-300"
                  style={{ width: `${utilPct}%` }}
                  title={`Utilization: ${utilPart.toFixed(4)} (${utilPct.toFixed(1)}%)`}
                />
                <div
                  className="bg-cyan-500 h-full transition-all duration-300"
                  style={{ width: `${latencyPct}%` }}
                  title={`Latency: ${latencyPart.toFixed(4)} (${latencyPct.toFixed(1)}%)`}
                />
              </div>

              {/* Raw vs Normalized metrics breakdown */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-2.5 pt-2 border-t border-slate-800/60 text-[11px] font-mono">
                <div className="text-slate-400">
                  <span className="text-emerald-400">Emissions:</span> {formatEmissions(rawCarbon, true, true)} &bull; n:{normCarbon.toFixed(2)}
                </div>
                <div className="text-slate-400">
                  <span className="text-blue-400">Duration:</span> {rawDuration.toFixed(1)}s &bull; n:{normDuration.toFixed(2)}
                </div>
                <div className="text-slate-400">
                  <span className="text-purple-400">Util:</span> {(projUtil * 100).toFixed(1)}% &bull; n:{normUtil.toFixed(2)}
                </div>
                <div className="text-slate-400">
                  <span className="text-cyan-400">Latency:</span> {rawLatency.toFixed(1)}ms &bull; n:{normLatency.toFixed(2)}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
