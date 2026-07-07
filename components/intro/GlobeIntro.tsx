'use client';

import { Canvas, useFrame } from '@react-three/fiber';
import { useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import { useAppStore } from '@/store/useAppStore';

/**
 * Cinematic entry — photoreal Earth (NASA Blue Marble + topography bump +
 * ocean specular), sun-lit terminator, volumetric-feel fresnel atmosphere.
 *
 * Camera choreography:
 *   Phase 1  slow orbital drift, wide shot
 *   Phase 2  Earth rotates Kerala into the light while the camera dollies in
 *   Phase 3  final push-in over the Malabar coast → dissolve to the live map
 *
 * Textures stream from a CDN; if they fail to load the intro degrades to a
 * stylized dark globe. Fully skippable; auto-skipped for prefers-reduced-motion.
 */

const KERALA_LAT = 10.3;
const KERALA_LON = 76.4;
const R = 2;

const TEX = {
  day: 'https://unpkg.com/three-globe@2.31.0/example/img/earth-blue-marble.jpg',
  bump: 'https://unpkg.com/three-globe@2.31.0/example/img/earth-topology.png',
  water: 'https://unpkg.com/three-globe@2.31.0/example/img/earth-water.png',
};

function latLonToVec3(lat: number, lon: number, r = R): THREE.Vector3 {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lon + 180) * (Math.PI / 180);
  return new THREE.Vector3(
    -r * Math.sin(phi) * Math.cos(theta),
    r * Math.cos(phi),
    r * Math.sin(phi) * Math.sin(theta)
  );
}

type Textures = { day: THREE.Texture; bump: THREE.Texture; water: THREE.Texture };

function useEarthTextures(): { textures: Textures | null; failed: boolean } {
  const [textures, setTextures] = useState<Textures | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const loader = new THREE.TextureLoader();
    loader.setCrossOrigin('anonymous');
    const load = (url: string) =>
      new Promise<THREE.Texture>((resolve, reject) => loader.load(url, resolve, undefined, reject));

    Promise.all([load(TEX.day), load(TEX.bump), load(TEX.water)])
      .then(([day, bump, water]) => {
        if (cancelled) return;
        day.colorSpace = THREE.SRGBColorSpace;
        day.anisotropy = 8;
        setTextures({ day, bump, water });
      })
      .catch(() => !cancelled && setFailed(true));

    return () => {
      cancelled = true;
    };
  }, []);

  return { textures, failed };
}

/** Fresnel atmosphere — the soft blue limb glow that sells "orbital camera". */
const atmosphereShader = {
  vertexShader: /* glsl */ `
    varying vec3 vNormal;
    varying vec3 vViewDir;
    void main() {
      vNormal = normalize(normalMatrix * normal);
      vec4 mvPos = modelViewMatrix * vec4(position, 1.0);
      vViewDir = normalize(-mvPos.xyz);
      gl_Position = projectionMatrix * mvPos;
    }
  `,
  fragmentShader: /* glsl */ `
    varying vec3 vNormal;
    varying vec3 vViewDir;
    void main() {
      float rim = 1.0 - abs(dot(vNormal, vViewDir));
      float glow = pow(rim, 3.5);
      gl_FragColor = vec4(vec3(0.30, 0.62, 1.0) * glow, glow * 0.9);
    }
  `,
};

function Earth({ textures }: { textures: Textures | null }) {
  return (
    <>
      <mesh rotation={[0, 0, 0]}>
        <sphereGeometry args={[R, 96, 96]} />
        {textures ? (
          <meshPhongMaterial
            map={textures.day}
            bumpMap={textures.bump}
            bumpScale={0.04}
            specularMap={textures.water}
            specular={new THREE.Color('#2a4a6a')}
            shininess={18}
          />
        ) : (
          <meshStandardMaterial color="#0d1b2e" roughness={0.85} metalness={0.05} />
        )}
      </mesh>
      {/* inner haze — thin shell just above the surface */}
      <mesh scale={1.012}>
        <sphereGeometry args={[R, 64, 64]} />
        <meshBasicMaterial color="#6ab7ff" transparent opacity={0.035} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
      {/* outer fresnel glow */}
      <mesh scale={1.13}>
        <sphereGeometry args={[R, 64, 64]} />
        <shaderMaterial
          args={[{
            vertexShader: atmosphereShader.vertexShader,
            fragmentShader: atmosphereShader.fragmentShader,
            transparent: true,
            side: THREE.BackSide,
            blending: THREE.AdditiveBlending,
            depthWrite: false,
          }]}
        />
      </mesh>
    </>
  );
}

function Beacon() {
  const ringRef = useRef<THREE.Mesh>(null);
  const pos = useMemo(() => latLonToVec3(KERALA_LAT, KERALA_LON, R * 1.012), []);
  const quat = useMemo(
    () => new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), pos.clone().normalize()),
    [pos]
  );

  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    if (ringRef.current) {
      const cycle = (t % 2) / 2;
      ringRef.current.scale.setScalar(0.6 + cycle * 2.4);
      (ringRef.current.material as THREE.MeshBasicMaterial).opacity = Math.max(0, 0.9 - cycle);
    }
  });

  return (
    <group position={pos} quaternion={quat}>
      <mesh>
        <circleGeometry args={[0.018, 24]} />
        <meshBasicMaterial color="#7dd3fc" transparent opacity={0.95} depthWrite={false} />
      </mesh>
      <mesh ref={ringRef}>
        <ringGeometry args={[0.028, 0.034, 48]} />
        <meshBasicMaterial color="#38bdf8" transparent opacity={0.9} side={THREE.DoubleSide} depthWrite={false} />
      </mesh>
    </group>
  );
}

function Stars() {
  const geometry = useMemo(() => {
    const g = new THREE.BufferGeometry();
    const n = 2500;
    const positions = new Float32Array(n * 3);
    const sizes = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const v = new THREE.Vector3().randomDirection().multiplyScalar(30 + Math.random() * 60);
      positions.set([v.x, v.y, v.z], i * 3);
      sizes[i] = Math.random();
    }
    g.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    return g;
  }, []);
  return (
    <points geometry={geometry}>
      <pointsMaterial color="#cdd8ee" size={0.08} sizeAttenuation transparent opacity={0.65} depthWrite={false} />
    </points>
  );
}

export default function GlobeIntro() {
  const finishIntro = useAppStore((s) => s.finishIntro);
  const [fading, setFading] = useState(false);
  const { textures, failed } = useEarthTextures();

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) finishIntro();
  }, [finishIntro]);

  const handleDone = () => {
    setFading(true);
    setTimeout(finishIntro, 900);
  };

  const texturesReady = textures !== null || failed;

  return (
    <div
      className={`fixed inset-0 z-50 bg-black transition-opacity duration-[900ms] ${fading ? 'pointer-events-none opacity-0' : 'opacity-100'}`}
      role="presentation"
    >
      <Canvas camera={{ position: [1.2, 0.75, 7.8], fov: 42 }} dpr={[1, 2]} gl={{ antialias: true }}>
        <Stars />
        <SceneWithTextures textures={textures} texturesReady={texturesReady} onDone={handleDone} />
        {/* Sun — key light, warm; space fill barely lifts the dark side */}
        <directionalLight position={[6, 2.2, 4.5]} intensity={2.6} color="#fff4e0" />
        <ambientLight intensity={0.09} color="#4a6a9a" />
      </Canvas>

      {/* Film grain / vignette for the cinematic read */}
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_55%,rgba(0,0,0,0.55)_100%)]" aria-hidden />

      <div className="pointer-events-none absolute inset-x-0 top-[10%] animate-fade-in text-center">
        <p className="font-mono text-[11px] uppercase tracking-[0.55em] text-accent/70">Disaster Intelligence</p>
        <h1 className="mt-3 font-display text-5xl font-bold tracking-tight text-white drop-shadow-[0_2px_24px_rgba(56,189,248,0.35)] md:text-7xl">
          VEGVISIR
        </h1>
        <p className="mt-3 text-sm text-ink-400">See the storm before it arrives · Kerala & South India</p>
      </div>

      {!texturesReady && (
        <p className="absolute bottom-24 left-1/2 -translate-x-1/2 font-mono text-[10px] uppercase tracking-widest text-ink-400">
          acquiring satellite view…
        </p>
      )}

      <button
        onClick={handleDone}
        className="absolute bottom-8 left-1/2 -translate-x-1/2 rounded-full border border-white/15 bg-white/5 px-6 py-2.5 text-sm text-ink-200 backdrop-blur transition hover:bg-white/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        Enter the map →
      </button>
    </div>
  );
}

/** Bridges texture state into the R3F tree (hooks can't cross the Canvas boundary). */
function SceneWithTextures({
  textures,
  texturesReady,
  onDone,
}: {
  textures: Textures | null;
  texturesReady: boolean;
  onDone: () => void;
}) {
  const globe = useRef<THREE.Group>(null);
  const done = useRef(false);
  const started = useRef<number | null>(null);

  const targetRot = useMemo(() => {
    const v = latLonToVec3(KERALA_LAT, KERALA_LON).normalize();
    return -Math.atan2(v.x, v.z);
  }, []);
  const resolved = useRef<number | null>(null);

  useFrame(({ camera, clock }, delta) => {
    if (!globe.current) return;
    if (started.current === null) {
      if (texturesReady) started.current = clock.elapsedTime;
      else {
        globe.current.rotation.y += delta * 0.06;
        return;
      }
    }
    const t = clock.elapsedTime - started.current;
    const g = globe.current;

    if (t < 1.6) {
      g.rotation.y += delta * 0.1;
      camera.position.x = THREE.MathUtils.damp(camera.position.x, 1.4, 1.2, delta);
    } else {
      if (resolved.current === null) {
        let target = targetRot;
        while (target < g.rotation.y) target += Math.PI * 2;
        resolved.current = target;
      }
      g.rotation.y = THREE.MathUtils.damp(g.rotation.y, resolved.current, 1.6, delta);
      camera.position.x = THREE.MathUtils.damp(camera.position.x, 0, 1.4, delta);
      camera.position.z = THREE.MathUtils.damp(camera.position.z, t < 4.6 ? 4.4 : 2.72, 1.9, delta);
      if (t > 6.4 && !done.current) {
        done.current = true;
        onDone();
      }
    }
    camera.lookAt(0, 0.32, 0);
  });

  return (
    <group ref={globe} rotation={[0.16, 0, 0]}>
      <Earth textures={textures} />
      <Beacon />
    </group>
  );
}
