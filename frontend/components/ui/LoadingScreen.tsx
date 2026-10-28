"use client";

import { useEffect, useState } from "react";
import { Leaf } from "lucide-react";

interface LoadingScreenProps {
  message?: string;
  submessage?: string;
  showProgress?: boolean;
  minDurationMs?: number;
}

export function LoadingScreen({
  message = "Initializing EcoRoute Telemetry...",
  submessage = "Connecting to real-time grid sensors and workload dispatcher",
  showProgress = true,
}: LoadingScreenProps) {
  const [progress, setProgress] = useState(15);

  useEffect(() => {
    if (!showProgress) return;
    const interval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 92) return 92;
        const inc = Math.floor(Math.random() * 12) + 4;
        return Math.min(92, prev + inc);
      });
    }, 250);
    return () => clearInterval(interval);
  }, [showProgress]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] p-8 text-center select-none font-sans relative">
      {/* Planetary ambient underglow */}
      <div className="absolute w-72 h-72 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute w-64 h-64 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none -bottom-8" />

      {/* 3D Circular Ring and Emblem */}
      <div className="relative w-28 h-28 flex items-center justify-center mb-6">
        {/* Outer Rotating Conic Laser Ring */}
        <div className="absolute inset-0 rounded-full border-2 border-dashed border-emerald-500/30 animate-[spin_8s_linear_infinite]" />

        {/* Dynamic Dual Glowing Rings */}
        <svg className="w-full h-full -rotate-90">
          <circle
            cx="56"
            cy="56"
            r="48"
            className="stroke-slate-900"
            strokeWidth="4"
            fill="transparent"
          />
          <circle
            cx="56"
            cy="56"
            r="48"
            className="stroke-emerald-400 transition-all duration-300"
            strokeWidth="4"
            strokeDasharray={301.6}
            strokeDashoffset={301.6 - (301.6 * (progress / 100))}
            strokeLinecap="round"
            fill="transparent"
          />
        </svg>

        {/* Inner Glass Emblem with EcoRoute Leaf Logo */}
        <div className="absolute w-16 h-16 rounded-2xl bg-gradient-to-b from-emerald-500/25 via-[#0c1628] to-[#040812] border border-emerald-400/50 flex items-center justify-center text-[#22c55e] shadow-[0_0_30px_rgba(34,197,94,0.35),inset_0_1px_0_rgba(255,255,255,0.3)] animate-pulse">
          <Leaf className="w-8 h-8 drop-shadow-[0_0_12px_rgba(34,197,94,0.9)] text-[#22c55e]" />
          {/* Orbiting Satellite Dot */}
          <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-[0_0_10px_#22c55e] animate-ping" />
          <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-emerald-400" />
        </div>
      </div>

      {/* Message & Status */}
      <div className="space-y-1.5 relative z-10 max-w-md">
        <h3 className="text-base sm:text-lg font-extrabold text-white tracking-tight flex items-center justify-center gap-2">
          {message}
        </h3>
        <p className="text-xs text-slate-400 font-mono leading-relaxed">{submessage}</p>
      </div>

      {/* Progress Bar & Percentage */}
      {showProgress && (
        <div className="w-64 sm:w-72 mt-6 space-y-2 relative z-10">
          <div className="h-1.5 w-full bg-slate-900/90 rounded-full overflow-hidden border border-slate-800/80 p-[1px]">
            <div
              className="h-full bg-gradient-to-r from-emerald-500 via-teal-400 to-[#22c55e] rounded-full transition-all duration-300 shadow-[0_0_12px_#22c55e]"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="flex items-center justify-between text-[11px] font-mono text-slate-500">
            <span>Loading resource</span>
            <span className="text-emerald-400 font-bold">{progress}%</span>
          </div>
        </div>
      )}
    </div>
  );
}
