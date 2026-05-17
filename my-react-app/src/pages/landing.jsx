import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import Globe from 'react-globe.gl'
import { TextureLoader, ShaderMaterial, Vector2 } from 'three'
import * as solar from 'solar-calculator'


// ISSUE: globe shading problem; attempt to fix if there's time
// ADDITIONS: 
// - Maybe add atmospheric glow around the globe
// - Check what else can be added to learn more section
const sunPosAt = (dt) => {
  const day = new Date(+dt).setUTCHours(0, 0, 0, 0)
  const t = solar.century(dt)
  const longitude = (day - dt) / 864e5 * 360 - 180

  return [
    longitude - solar.equationOfTime(t) / 4,
    solar.declination(t)
  ]
}

const initialNow = Date.now()

export default function LandingPage() {
  const navigate = useNavigate()
  const [now, setNow] = useState(initialNow)
  const [globeTime, setGlobeTime] = useState(initialNow)
  const [globeMaterial, setGlobeMaterial] = useState()

  // const globeRef = useRef(null)

  // useEffect(() => {
  //   const globe = globeRef.current
  //   let frame
  //   const animate = (ts) => {
  //     globe.style.transform = `
  //       translateY(${Math.sin(ts / 4000) * 6}px)
  //       translateX(${Math.cos(ts / 5000) * 4}px)
  //     `
  //     frame = requestAnimationFrame(animate)
  //   }
  //   frame = requestAnimationFrame(animate)
  //   return () => cancelAnimationFrame(frame)
  // }, [])

  const globeEl = useRef()
  const learnMoreRef = useRef(null)

  const scrollToLearnMore = () => {
    learnMoreRef.current?.scrollIntoView({
      behavior: 'smooth'
    })
  }

  useEffect(() => {
    if (!globeEl.current) return
  
    const controls = globeEl.current.controls()
  
    controls.autoRotate = true
    controls.autoRotateSpeed = 0.5

    // Adjust Rotating Globe Speed
    controls.enableDamping = true
    controls.dampingFactor = 0.05
    controls.rotateSpeed = 0.8
    controls.zoomSpeed = 0.8

    // Adjust altitude to change the zoomed view of the globe
    globeEl.current.pointOfView({ lat: 20, lng: 0, altitude: 2.0 })

  }, [])
  
  useEffect(() => {
    const id = setInterval(() => {
      setNow(Date.now())
    }, 1000)
  
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    let frame
  
    const animate = () => {
      setGlobeTime(t => t + 1000 * 60 * 2)
      frame = requestAnimationFrame(animate)
    }
  
    animate()
    return () => cancelAnimationFrame(frame)
  }, [])
  

  useEffect(() => {
    const loader = new TextureLoader()
  
    Promise.all([
      loader.loadAsync('//cdn.jsdelivr.net/npm/three-globe/example/img/earth-day.jpg'),
      loader.loadAsync('//cdn.jsdelivr.net/npm/three-globe/example/img/earth-night.jpg')
    ]).then(([dayTexture, nightTexture]) => {
      const material = new ShaderMaterial({
        uniforms: {
          dayTexture: { value: dayTexture },
          nightTexture: { value: nightTexture },
          sunPosition: { value: new Vector2() },
          globeRotation: { value: new Vector2() }
        },        
        vertexShader: `
          varying vec3 vNormal;
          varying vec2 vUv;
          void main() {
            vNormal = normalize(normalMatrix * normal);
            vUv = uv;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          }
        `,
        fragmentShader: `
        #define PI 3.141592653589793
        
        uniform sampler2D dayTexture;
        uniform sampler2D nightTexture;
        uniform vec2 sunPosition;
        uniform vec2 globeRotation;
        
        varying vec3 vNormal;
        varying vec2 vUv;
        
        float toRad(in float a) {
          return a * PI / 180.0;
        }
        
        vec3 Polar2Cartesian(in vec2 c) {
          float theta = toRad(90.0 - c.x);
          float phi = toRad(90.0 - c.y);
          return vec3(
            sin(phi) * cos(theta),
            cos(phi),
            sin(phi) * sin(theta)
          );
        }
        
        void main() {
          float invLon = toRad(globeRotation.x);
          float invLat = -toRad(globeRotation.y);
        
          mat3 rotX = mat3(
            1, 0, 0,
            0, cos(invLat), -sin(invLat),
            0, sin(invLat), cos(invLat)
          );
        
          mat3 rotY = mat3(
            cos(invLon), 0, sin(invLon),
            0, 1, 0,
            -sin(invLon), 0, cos(invLon)
          );
        
          vec3 rotatedSunDirection = rotX * rotY * Polar2Cartesian(sunPosition);
          float intensity = dot(normalize(vNormal), normalize(rotatedSunDirection));
        
          vec4 dayColor = texture2D(dayTexture, vUv);
          vec4 nightColor = texture2D(nightTexture, vUv);
        
          float blendFactor = smoothstep(-0.1, 0.1, intensity);
        
          // Adjust Globe Brightness:
          vec4 color = mix(nightColor, dayColor, blendFactor);
          color.rgb *= 0.80;
          // float edge = dot(normalize(vNormal), vec3(0.0, 0.0, 1.0));
          // color.rgb *= smoothstep(0.2, 1.0, edge);

          gl_FragColor = color;
        }
        `        
      })
  
      setGlobeMaterial(material)
    })
  }, [])
  
  useEffect(() => {
    if (!globeMaterial) return
  
    const [lng, lat] = sunPosAt(globeTime)
  
    globeMaterial.uniforms.sunPosition.value.set(lng, lat)
  }, [globeTime, globeMaterial])
  

  return (
    <>
      <section className="hero">
        {/* Makes the globe the background */}
        <div className="hero__bg">
          <Globe
            ref={globeEl}
            globeMaterial={globeMaterial}
            backgroundImageUrl="//cdn.jsdelivr.net/npm/three-globe/example/img/night-sky.png"
            width={window.innerWidth}
            height={window.innerHeight}
            onZoom={({ lng, lat }) => {
              if (globeMaterial) {
                globeMaterial.uniforms.globeRotation.value.set(lng, lat)
              }
            }}
          />
        </div>

        <div className="hero__content">
          <h1 className="hero__headline">
            Your next trip,<br />
            <em>planned in seconds!</em>
          </h1>

          <p className="hero__sub">Not hours.</p>

          <p className="hero__body">
            PlanIt turns your interests, budget, and dates into a complete day-by-day
            itinerary automatically. No more tab-hopping, no more guesswork.
          </p>

          <div className="hero__ctas">
            <button className="btn btn--primary" onClick={() => navigate('/signup')}>Start Planning for Free!</button>
            <button className="btn btn--secondary" onClick={scrollToLearnMore}>Learn More</button>
          </div>

          <div className="hero__stats">
            <div className="stat"><span className="stat__value">Free</span><span className="stat__label">For everyone</span></div>
            <div className="stat"><span className="stat__value">100%</span><span className="stat__label">Tailored to you</span></div>
            <div className="stat"><span className="stat__value">67k</span><span className="stat__label">Users in NY (and growing)</span></div>
          </div>

        </div>

        <div className="hero__time">
          {new Date(now).toLocaleString()}
        </div>

        {/* <div className="hero__globe-wrap">
          <div className="hero__globe" ref={globeRef}>
            <img
              src="https://upload.wikimedia.org/wikipedia/commons/thumb/9/97/The_Earth_seen_from_Apollo_17.jpg/1024px-The_Earth_seen_from_Apollo_17.jpg"
              alt="Earth"
              className="hero__globe-img"
            />
            <div className="hero__globe-glow" />
          </div>
        </div> */}
      </section>

      <section className="learn-more" ref={learnMoreRef}>
        <div className="learn-more__inner">

          <p className="learn-more__header">
            HOW IT WORKS
          </p>

          <h2 className="learn-more__title">
            Travel planning without the chaos.
          </h2>

          <p className="learn-more__text">
            PlanIt builds personalized itineraries based on your
            interests, budget, duration, and pace all in the span of seconds.
          </p>

          <div className="learn-more__grid">
            <div className="learn-card">
              <div className="learn-card__number">01</div>

              <h3>Create your account</h3>

              <p>
                Set up your profile and tell PlanIt how you like to travel.
              </p>
            </div>

            <div className="learn-card">
              <div className="learn-card__number">02</div>

              <h3>Answer a quick travel survey</h3>

              <p>
                Share your interests, budget, pace, and travel preferences.
              </p>
            </div>

            <div className="learn-card">
              <div className="learn-card__number">03</div>

              <h3>Enter your destination & dates</h3>

              <p>
                Choose where you're going and how long you're staying.
              </p>
            </div>

            <div className="learn-card">
              <div className="learn-card__number">04</div>

              <h3>Receive your personalized itinerary</h3>

              <p>
                Get a complete day-by-day plan built around your travel style.
              </p>
            </div>
          </div>
          <div className="learn-cta">
              <p className="learn-cta__top">Get Started</p>
              <h2 className="learn-cta__title">Your next trip starts here.</h2>
              <p className="learn-cta__sub">
                Join thousands of travelers who plan smarter with PlanIt.
              </p>
              <div className="learn-cta__actions">
                <button className="btn btn--primary" onClick={() => navigate('/signup')}>
                  Sign up now!
                </button>
              </div>
            </div>
        </div>
      </section>
      
    </>
  )
}
