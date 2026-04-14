import { useEffect, useRef } from 'react'
import * as THREE from 'three'

type HeroSceneProps = {
  className?: string
}

function HeroScene({ className }: HeroSceneProps) {
  const mountRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const mount = mountRef.current
    if (!mount) {
      return
    }

    const scene = new THREE.Scene()
    scene.fog = new THREE.FogExp2(0x020617, 0.036)

    const camera = new THREE.PerspectiveCamera(54, mount.clientWidth / mount.clientHeight, 0.1, 100)
    camera.position.set(0, 0.4, 6.2)

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setSize(mount.clientWidth, mount.clientHeight)
    renderer.outputColorSpace = THREE.SRGBColorSpace
    mount.appendChild(renderer.domElement)

    const group = new THREE.Group()
    scene.add(group)

    const coreGlobe = new THREE.Mesh(
      new THREE.SphereGeometry(1.3, 36, 36),
      new THREE.MeshStandardMaterial({
        color: 0x60a5fa,
        wireframe: true,
        transparent: true,
        opacity: 0.28,
        emissive: 0x0f172a,
        emissiveIntensity: 0.7,
        roughness: 0.38,
        metalness: 0.25,
      }),
    )
    group.add(coreGlobe)

    const orbitRing = new THREE.Mesh(
      new THREE.TorusGeometry(1.95, 0.025, 14, 96),
      new THREE.MeshBasicMaterial({
        color: 0x22d3ee,
        transparent: true,
        opacity: 0.65,
      }),
    )
    orbitRing.rotation.x = Math.PI * 0.35
    orbitRing.rotation.y = Math.PI * 0.2
    group.add(orbitRing)

    const plateGeometry = new THREE.BoxGeometry(0.8, 0.06, 0.38)
    const plateMaterial = new THREE.MeshStandardMaterial({
      color: 0x94a3b8,
      metalness: 0.42,
      roughness: 0.35,
      emissive: 0x0c4a6e,
      emissiveIntensity: 0.35,
    })

    const codePlates: THREE.Mesh[] = []
    for (let i = 0; i < 5; i += 1) {
      const plate = new THREE.Mesh(plateGeometry, plateMaterial.clone())
      plate.position.set(-2.3 + i * 1.15, -1.1 + (i % 2) * 0.35, -0.7 - Math.random() * 0.8)
      plate.rotation.y = (Math.random() - 0.5) * 0.5
      plate.rotation.x = -0.15 + Math.random() * 0.25
      codePlates.push(plate)
      group.add(plate)
    }

    const nodeVectors: THREE.Vector3[] = []
    for (let i = 0; i < 160; i += 1) {
      const theta = Math.random() * Math.PI * 2
      const phi = Math.acos((Math.random() * 2) - 1)
      const radius = 1.32 + Math.random() * 0.32
      nodeVectors.push(
        new THREE.Vector3(
          radius * Math.sin(phi) * Math.cos(theta),
          radius * Math.cos(phi),
          radius * Math.sin(phi) * Math.sin(theta),
        ),
      )
    }

    const nodesGeometry = new THREE.BufferGeometry().setFromPoints(nodeVectors)
    const nodes = new THREE.Points(
      nodesGeometry,
      new THREE.PointsMaterial({
        color: 0x67e8f9,
        size: 0.035,
        transparent: true,
        opacity: 0.95,
      }),
    )
    group.add(nodes)

    const linkPoints: THREE.Vector3[] = []
    for (let i = 0; i < nodeVectors.length - 1; i += 1) {
      if (i % 3 === 0) {
        linkPoints.push(nodeVectors[i], nodeVectors[(i + 7) % nodeVectors.length])
      }
      if (i % 11 === 0) {
        linkPoints.push(nodeVectors[i], nodeVectors[(i + 27) % nodeVectors.length])
      }
    }

    const linksGeometry = new THREE.BufferGeometry().setFromPoints(linkPoints)
    const links = new THREE.LineSegments(
      linksGeometry,
      new THREE.LineBasicMaterial({
        color: 0x38bdf8,
        transparent: true,
        opacity: 0.2,
      }),
    )
    group.add(links)

    const particlesCount = 760
    const particlesGeometry = new THREE.BufferGeometry()
    const positionArray = new Float32Array(particlesCount * 3)

    for (let i = 0; i < particlesCount; i += 1) {
      const i3 = i * 3
      const radius = 3.1 + Math.random() * 2.2
      const theta = Math.random() * Math.PI * 2
      const phi = Math.acos((Math.random() * 2) - 1)

      positionArray[i3] = radius * Math.sin(phi) * Math.cos(theta)
      positionArray[i3 + 1] = radius * Math.cos(phi)
      positionArray[i3 + 2] = radius * Math.sin(phi) * Math.sin(theta)
    }

    particlesGeometry.setAttribute('position', new THREE.BufferAttribute(positionArray, 3))

    const particles = new THREE.Points(
      particlesGeometry,
      new THREE.PointsMaterial({
        color: 0x93c5fd,
        size: 0.02,
        transparent: true,
        opacity: 0.55,
      }),
    )
    scene.add(particles)

    const keyLight = new THREE.DirectionalLight(0xe0f2fe, 1.5)
    keyLight.position.set(2.6, 2.8, 2.2)
    scene.add(keyLight)

    const fillLight = new THREE.DirectionalLight(0x60a5fa, 0.8)
    fillLight.position.set(-3.2, -1.1, -2)
    scene.add(fillLight)

    const rimLight = new THREE.PointLight(0x22d3ee, 1.4, 20)
    rimLight.position.set(0, 0.2, 4.2)
    scene.add(rimLight)

    const pointer = { x: 0, y: 0 }
    const onPointerMove = (event: PointerEvent) => {
      const bounds = mount.getBoundingClientRect()
      pointer.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1
      pointer.y = -(((event.clientY - bounds.top) / bounds.height) * 2 - 1)
    }

    mount.addEventListener('pointermove', onPointerMove)

    const clock = new THREE.Clock()
    let animationFrame = 0

    const animate = () => {
      const elapsed = clock.getElapsedTime()

      coreGlobe.rotation.y = elapsed * 0.11
      coreGlobe.rotation.z = Math.sin(elapsed * 0.24) * 0.12
      orbitRing.rotation.z = elapsed * 0.32
      orbitRing.rotation.y = elapsed * 0.18

      codePlates.forEach((plate, index) => {
        plate.position.y += Math.sin(elapsed * 0.9 + index * 0.8) * 0.0009
        plate.rotation.z = Math.sin(elapsed * 0.55 + index) * 0.08
      })

      group.rotation.y += (pointer.x * 0.45 - group.rotation.y) * 0.03
      group.rotation.x += (pointer.y * 0.22 - group.rotation.x) * 0.03

      particles.rotation.y = elapsed * 0.025
      particles.rotation.x = elapsed * 0.012

      camera.position.x += ((pointer.x * 0.26) - camera.position.x) * 0.03
      camera.position.y += ((pointer.y * 0.18) + 0.4 - camera.position.y) * 0.03
      camera.lookAt(0, 0, 0)

      renderer.render(scene, camera)
      animationFrame = window.requestAnimationFrame(animate)
    }

    animate()

    const onResize = () => {
      if (!mount) {
        return
      }
      const width = mount.clientWidth
      const height = mount.clientHeight
      renderer.setSize(width, height)
      camera.aspect = width / Math.max(height, 1)
      camera.updateProjectionMatrix()
    }

    window.addEventListener('resize', onResize)

    return () => {
      window.cancelAnimationFrame(animationFrame)
      window.removeEventListener('resize', onResize)
      mount.removeEventListener('pointermove', onPointerMove)

      scene.traverse((object: THREE.Object3D) => {
        const renderObject = object as THREE.Object3D & {
          geometry?: THREE.BufferGeometry
          material?: THREE.Material | THREE.Material[]
        }

        if (renderObject.geometry) {
          renderObject.geometry.dispose()
        }

        if (Array.isArray(renderObject.material)) {
          renderObject.material.forEach((material) => material.dispose())
        } else if (renderObject.material) {
          renderObject.material.dispose()
        }
      })

      renderer.dispose()
      if (renderer.domElement.parentElement === mount) {
        mount.removeChild(renderer.domElement)
      }
    }
  }, [])

  return <div className={className} ref={mountRef} aria-hidden="true" />
}

export default HeroScene
