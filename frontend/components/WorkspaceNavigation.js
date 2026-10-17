import { useEffect, useId, useRef, useState } from 'react';

export default function WorkspaceNavigation({ children }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const toggle = useRef(null);
  const navigation = useRef(null);

  useEffect(() => {
    if (!open) return;
    function closeOnEscape(event) {
      if (event.key === 'Escape') {
        setOpen(false);
        toggle.current?.focus();
      }
    }
    function closeOutside(event) {
      if (!navigation.current?.contains(event.target)) setOpen(false);
    }
    document.addEventListener('keydown', closeOnEscape);
    document.addEventListener('pointerdown', closeOutside);
    return () => {
      document.removeEventListener('keydown', closeOnEscape);
      document.removeEventListener('pointerdown', closeOutside);
    };
  }, [open]);

  return <nav ref={navigation} className="workspace-navigation" aria-label="Điều hướng không gian tài liệu" data-open={open}>
    <button ref={toggle} type="button" className="btn navigation-toggle" aria-expanded={open} aria-controls={id}
      aria-label={open ? 'Đóng menu điều hướng' : 'Mở menu điều hướng'} onClick={() => setOpen(!open)}>Menu</button>
    <div id={id} className="navigation-links" onClick={() => setOpen(false)}>{children}</div>
  </nav>;
}
