"use client";

import { useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Float, Points, PointMaterial } from "@react-three/drei";
import * as THREE from "three";

// Computed once at module load, not during render, so it stays pure with
// respect to React's render-purity rules while still only running once.
function generateStarPositions(count: number): Float32Array {
  const arr = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    const r = 6 + Math.random() * 10;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    arr[i * 3] = r * Math.sin(phi) * Math.cos(theta);
    arr[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
    arr[i * 3 + 2] = r * Math.cos(phi);
  }
  return arr;
}

const STAR_POSITIONS = generateStarPositions(1200);

/** Wireframe globe with an orbiting satellite point-cloud ring — the
 * landing page's hero centerpiece. Deliberately geometric/schematic rather
 * than photoreal, matching the "instrument, not marketing gloss" tone. */
function WireGlobe() {
  const meshRef = useRef<THREE.Mesh>(null);
  useFrame((_, delta) => {
    if (meshRef.current) meshRef.current.rotation.y += delta * 0.08;
  });
  return (
    <mesh ref={meshRef}>
      <sphereGeometry args={[1.3, 18, 18]} />
      <meshBasicMaterial color="#22d3aa" wireframe transparent opacity={0.16} />
    </mesh>
  );
}

function ScanRing() {
  const ref = useRef<THREE.Group>(null);
  useFrame((state, delta) => {
    if (ref.current) {
      ref.current.rotation.x += delta * 0.15;
      ref.current.rotation.z += delta * 0.05;
    }
  });
  return (
    <group ref={ref}>
      <mesh rotation={[Math.PI / 2.4, 0, 0]}>
        <torusGeometry args={[1.65, 0.003, 8, 128]} />
        <meshBasicMaterial color="#fdba46" transparent opacity={0.3} />
      </mesh>
      <mesh rotation={[Math.PI / 1.6, 0.4, 0]}>
        <torusGeometry args={[1.85, 0.002, 8, 128]} />
        <meshBasicMaterial color="#3b82f6" transparent opacity={0.25} />
      </mesh>
    </group>
  );
}

function StarField() {
  return (
    <Points positions={STAR_POSITIONS} stride={3} frustumCulled>
      <PointMaterial
        transparent
        color="#9aa0aa"
        size={0.02}
        sizeAttenuation
        depthWrite={false}
        opacity={0.6}
      />
    </Points>
  );
}

export function Globe3D() {
  return (
    <Canvas
      camera={{ position: [0, 0, 6.5], fov: 42 }}
      gl={{ antialias: true, alpha: true }}
      dpr={[1, 2]}
    >
      <ambientLight intensity={0.6} />
      <StarField />
      <Float speed={1.2} rotationIntensity={0.25} floatIntensity={0.5}>
        <group position={[0, -1.15, 0]}>
          <WireGlobe />
          <ScanRing />
        </group>
      </Float>
    </Canvas>
  );
}
