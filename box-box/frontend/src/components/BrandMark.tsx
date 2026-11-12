"use client";

import { useId } from "react";

/** The Box Box mark: a team-radio bubble with two pit-entry chevrons
 *  ("box, box" is the call to pit, always said twice). */
export default function BrandMark({ className = "w-9 h-9", title = "Box Box" }: { className?: string; title?: string }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg viewBox="0 0 64 64" className={className} role="img" aria-label={title}>
      <defs>
        <linearGradient id={`bb-fill-${id}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#FF3D2E" />
          <stop offset="1" stopColor="#B30500" />
        </linearGradient>
        <linearGradient id={`bb-shine-${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#FFFFFF" stopOpacity="0.28" />
          <stop offset="0.5" stopColor="#FFFFFF" stopOpacity="0" />
        </linearGradient>
      </defs>
      {/* Radio bubble, tail at the bottom left */}
      <path
        d="M15 5h34c6.1 0 11 4.9 11 11v23c0 6.1-4.9 11-11 11H31l-13 9.5c-.8.6-2 0-2-1V50h-1C8.9 50 4 45.1 4 39V16C4 9.9 8.9 5 15 5z"
        fill={`url(#bb-fill-${id})`}
      />
      <path
        d="M15 5h34c6.1 0 11 4.9 11 11v23c0 6.1-4.9 11-11 11H31l-13 9.5c-.8.6-2 0-2-1V50h-1C8.9 50 4 45.1 4 39V16C4 9.9 8.9 5 15 5z"
        fill={`url(#bb-shine-${id})`}
      />
      {/* Two chevrons: box, box */}
      <path d="M16.5 17h8.2l10 10.5-10 10.5h-8.2l10-10.5z" fill="#FFFFFF" />
      <path d="M31.5 17h8.2l10 10.5-10 10.5h-8.2l10-10.5z" fill="#FFFFFF" fillOpacity="0.6" />
    </svg>
  );
}
