import { useState, useEffect } from "react"
 
export default function useScrollDirection(threshold = 80) {
  const [visible, setVisible] = useState(true)
  const [lastY, setLastY]     = useState(0)
 
  useEffect(() => {
    const onScroll = () => {
      const y = window.scrollY
      if (y < threshold) {
        setVisible(true)           // tout en haut → toujours visible
      } else if (y < lastY) {
        setVisible(true)           // scroll vers le haut → affiche
      } else if (y > lastY + 5) {
        setVisible(false)          // scroll vers le bas → cache
      }
      setLastY(y)
    }
 
    window.addEventListener("scroll", onScroll, { passive: true })
    return () => window.removeEventListener("scroll", onScroll)
  }, [lastY, threshold])
 
  return visible
}