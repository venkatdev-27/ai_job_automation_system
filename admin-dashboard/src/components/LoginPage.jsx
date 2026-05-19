import React, { useState } from 'react';
import { Mail, Lock, Eye, EyeOff, LogIn, Sparkles, ArrowRight } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Please fill in all fields');
      return;
    }
    
    setLoading(true);
    setError('');
    
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      
      const data = await response.json();
      
      if (response.ok) {
        localStorage.setItem('token', data.token);
        localStorage.setItem('user', JSON.stringify(data.user));
        navigate('/');
      } else {
        setError(data.message || 'Login failed');
      }
    } catch (err) {
      setError('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-vh-100 d-flex align-items-center justify-content-center" style={{ background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f0f23 100%)' }}>
      {/* Background Effects */}
      <div style={{ position: 'fixed', inset: 0, overflow: 'hidden', pointerEvents: 'none' }}>
        <div style={{ position: 'absolute', top: '-20%', left: '-10%', width: '50%', height: '50%', background: 'radial-gradient(circle, rgba(115, 103, 240, 0.15) 0%, transparent 70%)', filter: 'blur(60px)' }}></div>
        <div style={{ position: 'absolute', bottom: '-20%', right: '-10%', width: '50%', height: '50%', background: 'radial-gradient(circle, rgba(16, 185, 129, 0.1) 0%, transparent 70%)', filter: 'blur(60px)' }}></div>
        <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', width: '60%', height: '60%', background: 'radial-gradient(circle, rgba(115, 103, 240, 0.05) 0%, transparent 70%)', filter: 'blur(80px)' }}></div>
      </div>

      <div className="position-relative" style={{ width: '100%', maxWidth: '440px', padding: '20px' }}>
        {/* Logo */}
        <div className="text-center mb-5">
          <div className="d-inline-flex align-items-center justify-content-center rounded-3 mb-4" style={{ width: 72, height: 72, background: 'linear-gradient(135deg, #7367f0, #a855f7)', boxShadow: '0 8px 32px rgba(115, 103, 240, 0.4)' }}>
            <Sparkles size={36} style={{ color: '#fff' }} />
          </div>
          <h2 className="mb-2 fw-bold" style={{ color: '#e2e8f0', fontSize: '28px' }}>Welcome Back</h2>
          <p style={{ color: '#64748b', fontSize: '14px' }}>Sign in to access your AI Strike Dashboard</p>
        </div>

        {/* Login Card */}
        <div className="card" style={{ backgroundColor: 'rgba(22, 33, 62, 0.8)', backdropFilter: 'blur(20px)', border: '1px solid rgba(115, 103, 240, 0.2)', borderRadius: '20px', boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)' }}>
          <div className="card-body p-5">
            <form onSubmit={handleSubmit}>
              {error && (
                <div className="alert d-flex align-items-center gap-2 mb-4" style={{ backgroundColor: 'rgba(239, 68, 68, 0.15)', border: '1px solid #ef4444', borderRadius: '10px', color: '#ef4444', fontSize: '13px' }}>
                  <Lock size={16} /> {error}
                </div>
              )}

              {/* Email Field */}
              <div className="mb-4">
                <label className="d-block mb-2" style={{ color: '#94a3b8', fontSize: '13px', fontWeight: 600 }}>Email Address</label>
                <div className="position-relative">
                  <Mail className="position-absolute" size={18} style={{ color: '#64748b', left: '16px', top: '50%', transform: 'translateY(-50%)', zIndex: 1 }} />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Enter your email"
                    style={{ 
                      width: '100%', padding: '14px 16px 14px 48px',
                      backgroundColor: '#0f0f23', border: '1px solid #1e293b',
                      borderRadius: '12px', color: '#e2e8f0', fontSize: '14px',
                      outline: 'none', transition: 'all 0.2s'
                    }}
                    onFocus={(e) => e.target.style.borderColor = '#7367f0'}
                    onBlur={(e) => e.target.style.borderColor = '#1e293b'}
                  />
                </div>
              </div>

              {/* Password Field */}
              <div className="mb-4">
                <label className="d-block mb-2" style={{ color: '#94a3b8', fontSize: '13px', fontWeight: 600 }}>Password</label>
                <div className="position-relative">
                  <Lock className="position-absolute" size={18} style={{ color: '#64748b', left: '16px', top: '50%', transform: 'translateY(-50%)', zIndex: 1 }} />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                    style={{ 
                      width: '100%', padding: '14px 48px 14px 48px',
                      backgroundColor: '#0f0f23', border: '1px solid #1e293b',
                      borderRadius: '12px', color: '#e2e8f0', fontSize: '14px',
                      outline: 'none', transition: 'all 0.2s'
                    }}
                    onFocus={(e) => e.target.style.borderColor = '#7367f0'}
                    onBlur={(e) => e.target.style.borderColor = '#1e293b'}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="position-absolute d-flex align-items-center justify-content-center"
                    style={{ background: 'none', border: 'none', color: '#64748b', right: '16px', top: '50%', transform: 'translateY(-50%)', cursor: 'pointer', zIndex: 1 }}
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>

              {/* Remember & Forgot */}
              <div className="d-flex justify-content-between align-items-center mb-4">
                <label className="d-flex align-items-center gap-2" style={{ cursor: 'pointer' }}>
                  <input type="checkbox" style={{ width: '16px', height: '16px', accentColor: '#7367f0' }} />
                  <span style={{ color: '#64748b', fontSize: '13px' }}>Remember me</span>
                </label>
                <a href="#" style={{ color: '#7367f0', fontSize: '13px', textDecoration: 'none' }}>Forgot password?</a>
              </div>

              {/* Submit Button */}
              <button
                type="submit"
                disabled={loading}
                className="btn w-100 d-flex align-items-center justify-content-center gap-2"
                style={{ 
                  background: loading ? '#334155' : 'linear-gradient(135deg, #7367f0, #a855f7)',
                  border: 'none', borderRadius: '12px', color: '#fff', fontWeight: 700, fontSize: '15px',
                  padding: '14px 24px', cursor: loading ? 'not-allowed' : 'pointer',
                  boxShadow: loading ? 'none' : '0 4px 20px rgba(115, 103, 240, 0.4)',
                  transition: 'all 0.3s'
                }}
              >
                {loading ? (
                  <div className="spinner-border spinner-border-sm" role="status">
                    <span className="visually-hidden"></span>
                  </div>
                ) : (
                  <>
                    <LogIn size={18} /> Sign In
                  </>
                )}
              </button>
            </form>

            {/* Divider */}
            <div className="d-flex align-items-center gap-3 my-4">
              <div style={{ flex: 1, height: '1px', backgroundColor: '#1e293b' }}></div>
              <span style={{ color: '#64748b', fontSize: '12px' }}>OR</span>
              <div style={{ flex: 1, height: '1px', backgroundColor: '#1e293b' }}></div>
            </div>

            {/* Sign Up Link */}
            <p className="text-center mb-0" style={{ color: '#64748b', fontSize: '14px' }}>
              Don't have an account?{' '}
              <Link to="/signup" style={{ color: '#7367f0', fontWeight: 600, textDecoration: 'none' }}>
                Create Account <ArrowRight size={14} style={{ marginLeft: '4px' }} />
              </Link>
            </p>
          </div>
        </div>

        {/* Footer */}
        <p className="text-center mt-4" style={{ color: '#475569', fontSize: '12px' }}>
          By signing in, you agree to our Terms of Service and Privacy Policy
        </p>
      </div>
    </div>
  );
}