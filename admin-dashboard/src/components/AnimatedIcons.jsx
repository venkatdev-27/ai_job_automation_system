import React from 'react';
import { Loader2, Bell, RefreshCcw } from 'lucide-react';

export function AnimatedLoader({ size = 14, className = '', style = {} }) {
  return (
    <Loader2 
      size={size} 
      className={`animate-spin ${className}`}
      style={{ ...style }}
    />
  );
}

export function AnimatedLoaderOnHover({ size = 14, className = '', style = {} }) {
  return (
    <Loader2 
      size={size} 
      className={className}
      style={{ ...style }}
      onMouseEnter={(e) => e.currentTarget.classList.add('animate-spin')}
      onMouseLeave={(e) => e.currentTarget.classList.remove('animate-spin')}
    />
  );
}

export function AnimatedBell({ size = 20, count = 0, className = '', style = {} }) {
  const [animate, setAnimate] = React.useState(false);
  const prevCount = React.useRef(count);

  React.useEffect(() => {
    if (count > prevCount.current) {
      setAnimate(true);
      const timer = setTimeout(() => setAnimate(false), 500);
      return () => clearTimeout(timer);
    }
    prevCount.current = count;
  }, [count]);

  return (
    <div className="position-relative d-inline-flex" style={style}>
      <Bell 
        size={size} 
        className={animate ? 'animate-bell-shake' : ''}
        style={{ color: '#e2e8f0' }}
      />
      {count > 0 && (
        <span 
          className="position-absolute d-flex align-items-center justify-content-center rounded-circle bg-danger text-white fw-bold"
          style={{
            top: '-6px',
            right: '-6px',
            minWidth: '18px',
            height: '18px',
            padding: '0 4px',
            fontSize: '10px',
            fontWeight: 700,
            border: '2px solid #16213e'
          }}
        >
          {count > 9 ? '9+' : count}
        </span>
      )}
    </div>
  );
}

export function AnimatedRefreshCcw({ size = 20, className = '', style = {}, onClick }) {
  const [animate, setAnimate] = React.useState(false);

  const handleClick = (e) => {
    setAnimate(true);
    onClick?.(e);
  };

  return (
    <RefreshCcw 
      size={size} 
      className={animate ? 'animate-rotate-ccw' : ''}
      style={{ 
        color: '#e2e8f0', 
        cursor: 'pointer',
        transition: 'color 0.2s',
        ...style 
      }}
      onClick={handleClick}
      onAnimationEnd={() => setAnimate(false)}
    />
  );
}

export function AnimateIcon({ children, animateOnHover = false, className = '' }) {
  const [isHovered, setIsHovered] = React.useState(false);

  const child = React.Children.only(children);
  const cloned = React.cloneElement(child, {
    className: `${child.props.className || ''} ${animateOnHover && isHovered ? 'animate-spin' : ''} ${className}`,
    onMouseEnter: (e) => {
      setIsHovered(true);
      child.props.onMouseEnter?.(e);
    },
    onMouseLeave: (e) => {
      setIsHovered(false);
      child.props.onMouseLeave?.(e);
    }
  });

  return cloned;
}