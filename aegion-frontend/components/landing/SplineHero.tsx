"use client";

import React, { Suspense, useRef, useEffect, useState } from "react";

/* ══════════════════════════════════════════════════════════════
   SPLINE HERO — 3D Interactive Scene
   
   Wraps Spline viewer with:
   - Lazy loading (Suspense boundary)
   - Fallback canvas particle animation
   - Mouse-responsive parallax on the wrapper
   ══════════════════════════════════════════════════════════════ */

const SPLINE_SCENE_URL = "https://prod.spline.design/6Wq1Q7YGyM-iab9i/scene.splinecode";

// Lazy import Spline to avoid SSR issues
const Spline = React.lazy(() => import("@splinetool/react-spline"));

function ParticleFallback() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const resize = () => {
      canvas.width = canvas.offsetWidth * dpr;
      canvas.height = canvas.offsetHeight * dpr;
      ctx.scale(dpr, dpr);
    };
    resize();
    window.addEventListener("resize", resize);

    // Create particles
    const particles: Array<{
      x: number; y: number; vx: number; vy: number;
      r: number; opacity: number; hue: number;
    }> = [];
    
    for (let i = 0; i < 120; i++) {
      particles.push({
        x: Math.random() * canvas.offsetWidth,
        y: Math.random() * canvas.offsetHeight,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        r: Math.random() * 2 + 0.5,
        opacity: Math.random() * 0.5 + 0.1,
        hue: 250 + Math.random() * 80, // violet to magenta range
      });
    }

    let animId: number;
    const animate = () => {
      const w = canvas.offsetWidth;
      const h = canvas.offsetHeight;
      ctx.clearRect(0, 0, w, h);

      // Draw connections
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 100) {
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = `hsla(260, 100%, 70%, ${0.06 * (1 - dist / 100)})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      }

      // Draw & update particles
      for (const p of particles) {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0 || p.x > w) p.vx *= -1;
        if (p.y < 0 || p.y > h) p.vy *= -1;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${p.hue}, 100%, 70%, ${p.opacity})`;
        ctx.fill();
      }

      animId = requestAnimationFrame(animate);
    };
    animate();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="w-full h-full"
      style={{ opacity: 0.6 }}
    />
  );
}

export function SplineHero() {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [loaded, setLoaded] = useState(false);
  const [splineError, setSplineError] = useState(false);

  // Mouse parallax on wrapper
  useEffect(() => {
    const wrapper = wrapperRef.current;
    if (!wrapper) return;

    const handleMouse = (e: MouseEvent) => {
      const rect = wrapper.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width - 0.5) * 8;
      const y = ((e.clientY - rect.top) / rect.height - 0.5) * 8;
      wrapper.style.transform = `perspective(1000px) rotateY(${x}deg) rotateX(${-y}deg)`;
    };

    const handleLeave = () => {
      wrapper.style.transform = "perspective(1000px) rotateY(0deg) rotateX(0deg)";
    };

    wrapper.addEventListener("mousemove", handleMouse);
    wrapper.addEventListener("mouseleave", handleLeave);
    return () => {
      wrapper.removeEventListener("mousemove", handleMouse);
      wrapper.removeEventListener("mouseleave", handleLeave);
    };
  }, []);

  return (
    <div
      ref={wrapperRef}
      className="w-full h-[500px] md:h-[600px] relative"
      style={{
        transition: "transform 0.3s ease-out",
        transformStyle: "preserve-3d",
      }}
    >
      {/* Atmospheric glow behind the scene */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: `
            radial-gradient(ellipse at 50% 50%, hsla(260, 100%, 50%, 0.12), transparent 60%),
            radial-gradient(ellipse at 30% 70%, hsla(330, 100%, 50%, 0.06), transparent 50%)
          `,
        }}
      />

      {/* Spline scene with particle fallback */}
      <div className="relative z-10 w-full h-full">
        {!splineError ? (
          <Suspense fallback={<ParticleFallback />}>
            <Spline
              scene={SPLINE_SCENE_URL}
              onLoad={() => setLoaded(true)}
              onError={() => setSplineError(true)}
              style={{
                width: "100%",
                height: "100%",
                opacity: loaded ? 1 : 0,
                transition: "opacity 1s ease-in",
              }}
            />
            {!loaded && (
              <div className="absolute inset-0">
                <ParticleFallback />
              </div>
            )}
          </Suspense>
        ) : (
          <ParticleFallback />
        )}
      </div>
    </div>
  );
}
