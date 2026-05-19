import React, { useState } from 'react';
import { Mail, Lock, User, Phone, Eye, EyeOff, UserPlus, Sparkles, ArrowRight, ArrowLeft, Check } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';

export default function SignupPage() {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    gender: 'male',
    password: '',
    confirmPassword: ''
  });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.name || !formData.email || !formData.password) {
      setError('Please fill in all required fields');
      return;
    }

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (formData.password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }
    
    setLoading(true);
    setError('');
    
    try {
      const response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: formData.name,
          email: formData.email,
          phone: formData.phone,
          gender: formData.gender,
          password: formData.password
        })
      });
      
      const data = await response.json();
      
      if (response.ok) {
        localStorage.setItem('token', data.token);
        localStorage.setItem('user', JSON.stringify(data.user));
        navigate('/');
      } else {
        setError(data.message || 'Registration failed');
      }
    } catch (err) {
      setError('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const inputFields = [
    { name: 'name', label: 'Full Name', icon: User, placeholder: 'Enter your name', type: 'text', required: true },
    { name: 'email', label: 'Email Address', icon: Mail, placeholder: 'Enter your email', type: 'email', required: true },
    { name: 'phone', label: 'Phone Number', icon: Phone, placeholder: 'Enter your phone', type: 'tel', required: false },
  ];

  const passwordRequirements = [
    { met: formData.password.length >= 6, text: 'At least 6 characters' },
    { met: /[A-Z]/.test(formData.password), text: 'One uppercase letter' },
    { met: /[0-9]/.test(formData.password), text: 'One number' },
  ];

  return (
    <div className="min-vh-100 d-flex align-items-center justify-content-center" style={{ background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f0f23 100%)' }}>
      {/* Background Effects */}
      <div style={{ position: 'fixed', inset: 0, overflow: 'hidden', pointerEvents: 'none' }}>
        <div style={{ position: 'absolute', top: '-20%', right: '-10%', width: '50%', height: '50%', background: 'radial-gradient(circle, rgba(16, 185, 129, 0.15) 0%, transparent 70%)', filter: 'blur(60px)' }}></div>
        <div style={{ position: 'absolute', bottom: '-20%', left: '-10%', width: '50%', height: '50%', background: 'radial-gradient(circle, rgba(115, 103, 240, 0.1) 0%, transparent 70%)', filter: 'blur(60px)' }}></div>
      </div>

      <div className="position-relative" style={{ width: '100%', maxWidth: '480px', padding: '20px' }}>
        {/* Logo */}
        <div className="text-center mb-5">
          <div className="d-inline-flex align-items-center justify-content-center rounded-3 mb-4" style={{ width: 72, height: 72, background: 'linear-gradient(135deg, #10b981, #059669)', boxShadow: '0 8px 32px rgba(16, 185, 129, 0.4)' }}>
            <Sparkles size={36} style={{ color: '#fff' }} />
          </div>
          <h2 className="mb-2 fw-bold" style={{ color: '#e2e8f0', fontSize: '28px' }}>Create Account</h2>
          <p style={{ color: '#64748b', fontSize: '14px' }}>Join AI Strike Dashboard today</p>
        </div>

        {/* Signup Card */}
        <div className="card" style={{ backgroundColor: 'rgba(22, 33, 62, 0.8)', backdropFilter: 'blur(20px)', border: '1px solid rgba(16, 185, 129, 0.2)', borderRadius: '20px', boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)' }}>
          <div className="card-body p-5">
            <form onSubmit={handleSubmit}>
              {error && (
                <div className="alert d-flex align-items-center gap-2 mb-4" style={{ backgroundColor: 'rgba(239, 68, 68, 0.15)', border: '1px solid #ef4444', borderRadius: '10px', color: '#ef4444', fontSize: '13px' }}>
                  <Lock size={16} /> {error}
                </div>
              )}

              {/* Input Fields */}
              {inputFields.map((field) => (
                <div className="mb-4" key={field.name}>
                  <label className="d-block mb-2" style={{ color: '#94a3b8', fontSize: '13px', fontWeight: 600 }}>
                    {field.label} {field.required && <span style={{ color: '#ef4444' }}> *</span>}
                  </label>
                  <div className="position-relative">
                    <field.icon className="position-absolute" size={18} style={{ color: '#64748b', left: '16px', top: '50%', transform: 'translateY(-50%)', zIndex: 1 }} />
                    <input
                      type={field.type}
                      name={field.name}
                      value={formData[field.name]}
                      onChange={handleChange}
                      placeholder={field.placeholder}
                      style={{ 
                        width: '100%', padding: '14px 16px 14px 48px',
                        backgroundColor: '#0f0f23', border: '1px solid #1e293b',
                        borderRadius: '12px', color: '#e2e8f0', fontSize: '14px',
                        outline: 'none', transition: 'all 0.2s'
                      }}
                      onFocus={(e) => e.target.style.borderColor = '#10b981'}
                      onBlur={(e) => e.target.style.borderColor = '#1e293b'}
                    />
                  </div>
                </div>
              ))}

              {/* Gender Field */}
              <div className="mb-4">
                <label className="d-block mb-2" style={{ color: '#94a3b8', fontSize: '13px', fontWeight: 600 }}>Gender</label>
                <div className="d-flex gap-3">
                  {['male', 'female', 'other'].map((g) => (
                    <label key={g} className="d-flex align-items-center gap-2" style={{ cursor: 'pointer' }}>
                      <input
                        type="radio"
                        name="gender"
                        value={g}
                        checked={formData.gender === g}
                        onChange={handleChange}
                        style={{ accentColor: '#10b981' }}
                      />
                      <span style={{ color: '#e2e8f0', textTransform: 'capitalize' }}>{g}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Password Field */}
              <div className="mb-3">
                <label className="d-block mb-2" style={{ color: '#94a3b8', fontSize: '13px', fontWeight: 600 }}>Password <span style={{ color: '#ef4444' }}> *</span></label>
                <div className="position-relative">
                  <Lock className="position-absolute" size={18} style={{ color: '#64748b', left: '16px', top: '50%', transform: 'translateY(-50%)', zIndex: 1 }} />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    name="password"
                    value={formData.password}
                    onChange={handleChange}
                    placeholder="create your password"
                    style={{ 
                      width: '100%', padding: '14px 48px 14px 48px',
                      backgroundColor: '#0f0f23', border: '1px solid #1e293b',
                      borderRadius: '12px', color: '#e2e8f0', fontSize: '14px',
                      outline: 'none', transition: 'all 0.2s'
                    }}
                    onFocus={(e) => e.target.style.borderColor = '#10b981'}
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

              {/* Password Requirements */}
              {formData.password && (
                <div className="mb-4">
                  <div className="d-flex flex-wrap gap-2">
                    {passwordRequirements.map((req, i) => (
                      <div key={i} className="d-flex align-items-center gap-1" style={{ fontSize: '11px', color: req.met ? '#10b981' : '#64748b' }}>
                        <Check size={12} style={{ color: req.met ? '#10b981' : '#64748b' }} /> {req.text}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Confirm Password */}
              <div className="mb-4">
                <label className="d-block mb-2" style={{ color: '#94a3b8', fontSize: '13px', fontWeight: 600 }}>Confirm Password <span style={{ color: '#ef4444' }}> *</span></label>
                <div className="position-relative">
                  <Lock className="position-absolute" size={18} style={{ color: '#64748b', left: '16px', top: '50%', transform: 'translateY(-50%)', zIndex: 1 }} />
                  <input
                    type="password"
                    name="confirmPassword"
                    value={formData.confirmPassword}
                    onChange={handleChange}
                    placeholder="Confirm your password"
                    style={{ 
                      width: '100%', padding: '14px 16px 14px 48px',
                      backgroundColor: '#0f0f23', border: '1px solid #1e293b',
                      borderRadius: '12px', color: '#e2e8f0', fontSize: '14px',
                      outline: 'none', transition: 'all 0.2s',
                      borderColor: formData.confirmPassword && formData.password === formData.confirmPassword ? '#10b981' : '#1e293b'
                    }}
                    onFocus={(e) => e.target.style.borderColor = '#10b981'}
                    onBlur={(e) => e.target.style.borderColor = formData.confirmPassword && formData.password === formData.confirmPassword ? '#10b981' : '#1e293b'}
                  />
                  {formData.confirmPassword && formData.password === formData.confirmPassword && (
                    <Check size={18} className="position-absolute" style={{ color: '#10b981', right: '16px', top: '50%', transform: 'translateY(-50%)' }} />
                  )}
                </div>
              </div>

              {/* Submit Button */}
              <button
                type="submit"
                disabled={loading}
                className="btn w-100 d-flex align-items-center justify-content-center gap-2"
                style={{ 
                  background: loading ? '#334155' : 'linear-gradient(135deg, #10b981, #059669)',
                  border: 'none', borderRadius: '12px', color: '#fff', fontWeight: 700, fontSize: '15px',
                  padding: '14px 24px', cursor: loading ? 'not-allowed' : 'pointer',
                  boxShadow: loading ? 'none' : '0 4px 20px rgba(16, 185, 129, 0.4)',
                  transition: 'all 0.3s'
                }}
              >
                {loading ? (
                  <div className="spinner-border spinner-border-sm" role="status">
                    <span className="visually-hidden"></span>
                  </div>
                ) : (
                  <>
                    <UserPlus size={18} /> Create Account
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

            {/* Sign In Link */}
            <p className="text-center mb-0" style={{ color: '#64748b', fontSize: '14px' }}>
              Already have an account?{' '}
              <Link to="/login" style={{ color: '#10b981', fontWeight: 600, textDecoration: 'none' }}>
                Sign In <ArrowRight size={14} style={{ marginLeft: '4px' }} />
              </Link>
            </p>
          </div>
        </div>

        {/* Back to Home */}
        <div className="text-center mt-4">
          <Link to="/" className="d-inline-flex align-items-center gap-2" style={{ color: '#64748b', textDecoration: 'none', fontSize: '14px' }}>
            <ArrowLeft size={16} /> Back to Home
          </Link>
        </div>
      </div>
    </div>
  );
}