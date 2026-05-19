import { useState } from 'react';
import api from '../services/api';

// ─── Reusable Input ────────────────────────────────────────────────────────────
const Field = ({ label, id, type = 'text', placeholder, value, onChange, required }) => (
  <div className="flex flex-col gap-1.5">
    <label htmlFor={id} className="text-sm font-medium text-slate-700">
      {label} {required && <span className="text-orange-500">*</span>}
    </label>
    <input
      id={id}
      type={type}
      placeholder={placeholder}
      value={value}
      onChange={onChange}
      required={required}
      className="bg-white border border-slate-200 rounded-lg px-4 py-2.5 text-slate-800
                 placeholder:text-slate-400 focus:border-orange-500 focus:ring-2 focus:ring-orange-500/20
                 transition-all duration-200 text-sm w-full"
    />
  </div>
);

// ─── Credential Pair ───────────────────────────────────────────────────────────
const CredentialBlock = ({ platform, icon, labelText, type, placeholder, values, onChange }) => (
  <div className="bg-orange-50/50 border border-orange-100 rounded-xl p-4 sm:p-5 space-y-3
                  hover:border-orange-300 transition-colors duration-200">
    <div className="flex items-center gap-2 mb-1">
      <span className="text-lg">{icon}</span>
      <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wider">{platform}</h3>
    </div>
    <Field
      label={labelText}
      id={`${platform}-username`}
      type={type}
      placeholder={placeholder}
      value={values.username}
      onChange={(e) => onChange('username', e.target.value)}
    />
    <Field
      label="Password"
      id={`${platform}-password`}
      type="password"
      placeholder={`Enter ${platform} password`}
      value={values.password}
      onChange={(e) => onChange('password', e.target.value)}
    />
  </div>
);

// ─── Main Component ────────────────────────────────────────────────────────────
export default function StudentForm() {
  const [form, setForm] = useState({
    name: '', email: '', phone: '', gender: '',
    linkedin:    { username: '', password: '' },
    naukri:      { username: '', password: '' },
    foundit:     { username: '', password: '' },
  });
  const [resume, setResume] = useState(null);
  const [status, setStatus] = useState({ type: '', message: '' }); // type: 'success'|'error'|'loading'

  const handleField = (key, value) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const handleCredential = (platform, field, value) =>
    setForm((prev) => ({
      ...prev,
      [platform]: { ...prev[platform], [field]: value },
    }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus({ type: 'loading', message: 'Registering student…' });

    const data = new FormData();
    data.append('name',   form.name);
    data.append('email',  form.email);
    data.append('phone',  form.phone);
    data.append('gender', form.gender);

    // Credentials — flat keys the controller expects
    data.append('linkedinUsername',   form.linkedin.username);
    data.append('linkedinPassword',   form.linkedin.password);
    data.append('naukriUsername',     form.naukri.username);
    data.append('naukriPassword',     form.naukri.password);
    data.append('founditUsername',    form.foundit.username);
    data.append('founditPassword',    form.foundit.password);

    if (resume) data.append('resume', resume);

    try {
      const res = await api.post('/api/students/register', data);
      setStatus({ 
        type: 'success', 
        message: 'Registered successfully! 🎉 The AI Warmup Pipeline has started generating your tailored resumes in the background.' 
      });
      // Reset form
      setForm({
        name: '', email: '', phone: '', gender: '',
        linkedin: { username: '', password: '' },
        naukri:   { username: '', password: '' },
        foundit:  { username: '', password: '' },
      });
      setResume(null);
      e.target.reset();
    } catch (err) {
      const msg = err.response?.data?.message || 'Something went wrong. Please try again.';
      setStatus({ type: 'error', message: msg });
    }
  };

  const platforms = [
    { key: 'linkedin',    label: 'LinkedIn',    icon: '🔗', labelText: 'Mobile Number', type: 'tel', placeholder: 'Enter LinkedIn mobile number' },
    { key: 'naukri',      label: 'Naukri',      icon: '🏢', labelText: 'Email / Username', type: 'text', placeholder: 'Enter Naukri email/username' },
    { key: 'foundit',     label: 'Foundit',     icon: '🔍', labelText: 'Email / Username', type: 'text', placeholder: 'Enter Foundit email/username' },
  ];

  return (
    <div className="min-h-screen bg-orange-50 py-6 sm:py-12 px-3 sm:px-4">
      {/* Header */}
      <div className="text-center mb-6 sm:mb-10">
        <div className="inline-flex items-center gap-2 bg-orange-100/80 border border-orange-200
                        rounded-full px-3 py-1 sm:px-4 sm:py-1.5 text-orange-700 text-xs sm:text-sm font-medium mb-3 sm:mb-4">
          🤖 PlacementBot AI
        </div>
        <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold text-slate-800 mb-2">
          Student Registration
        </h1>
        <p className="text-slate-500 text-xs sm:text-sm max-w-md mx-auto px-2">
          Fill in your details and platform credentials so PlacementBot can apply to jobs on your behalf.
        </p>
      </div>

      {/* Card */}
      <form
        onSubmit={handleSubmit}
        className="max-w-3xl mx-auto bg-white border border-orange-100 rounded-xl sm:rounded-2xl
                   shadow-xl shadow-orange-900/5 overflow-hidden"
      >
        {/* Section: Personal Info */}
        <div className="px-4 sm:px-6 py-4 sm:py-5 border-b border-orange-100">
          <h2 className="text-xs font-semibold text-orange-600 uppercase tracking-widest mb-4 sm:mb-5">
            Personal Information
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-5">
            <Field label="Full Name" id="name" placeholder="Enter full name" value={form.name}
              onChange={(e) => handleField('name', e.target.value)} required />
            <Field label="Email Address" id="email" type="email" placeholder="Enter email address"
              value={form.email} onChange={(e) => handleField('email', e.target.value)} required />
            <Field label="Mobile Number" id="phone" placeholder="Enter mobile number"
              value={form.phone} onChange={(e) => handleField('phone', e.target.value)} required />

            {/* Gender */}
            <div className="flex flex-col gap-1.5">
              <label htmlFor="gender" className="text-sm font-medium text-slate-700">
                Gender <span className="text-orange-500">*</span>
              </label>
              <select
                id="gender"
                value={form.gender}
                onChange={(e) => handleField('gender', e.target.value)}
                required
                className="bg-white border border-slate-200 rounded-lg px-4 py-2.5 text-slate-800
                           focus:border-orange-500 focus:ring-2 focus:ring-orange-500/20
                           transition-all duration-200 text-sm appearance-none cursor-pointer w-full"
              >
                <option value="" disabled>Select gender</option>
                <option value="Male">Male</option>
                <option value="Female">Female</option>
                <option value="Other">Other</option>
                <option value="Prefer not to say">Prefer not to say</option>
              </select>
            </div>
          </div>
        </div>

        {/* Section: Resume Upload */}
        <div className="px-4 sm:px-6 py-4 sm:py-5 border-b border-orange-100">
          <h2 className="text-xs font-semibold text-orange-600 uppercase tracking-widest mb-4 sm:mb-5">
            Resume Upload
          </h2>
          <label
            htmlFor="resume"
            className="flex flex-col items-center justify-center w-full h-32 sm:h-36 border-2 border-dashed
                       border-orange-200 rounded-xl cursor-pointer bg-orange-50/30
                       hover:border-orange-400 hover:bg-orange-50 transition-all duration-200 group p-4"
          >
            <div className="text-center">
              <div className="text-2xl sm:text-3xl mb-2">{resume ? '📄' : '📁'}</div>
              <p className="text-xs sm:text-sm text-slate-500 group-hover:text-slate-700 transition-colors">
                {resume
                  ? <span className="text-orange-600 font-medium">{resume.name}</span>
                  : <><span className="text-orange-600 font-medium">Click to upload</span> your resume</>}
              </p>
              <p className="text-[10px] sm:text-xs text-slate-400 mt-1">PDF, DOC, DOCX — max 5MB</p>
            </div>
            <input
              id="resume"
              type="file"
              accept=".pdf,.doc,.docx"
              className="hidden"
              onChange={(e) => setResume(e.target.files[0] || null)}
            />
          </label>
        </div>

        {/* Section: Platform Credentials */}
        <div className="px-4 sm:px-6 py-4 sm:py-5">
          <h2 className="text-xs font-semibold text-orange-600 uppercase tracking-widest mb-3 sm:mb-5">
            Platform Credentials
          </h2>
          <p className="text-xs text-slate-500 mb-4 sm:mb-5 leading-relaxed">
            🔒 Your credentials are stored securely and only used for automated job applications.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4">
            {platforms.map(({ key, label, icon, labelText, type, placeholder }) => (
              <CredentialBlock
                key={key}
                platform={label}
                icon={icon}
                labelText={labelText}
                type={type}
                placeholder={placeholder}
                values={form[key]}
                onChange={(field, value) => handleCredential(key, field, value)}
              />
            ))}
          </div>
        </div>

        {/* Status Banner */}
        {status.message && (
          <div className={`mx-4 sm:mx-6 mb-4 px-3 sm:px-4 py-2 sm:py-3 rounded-lg text-xs sm:text-sm font-medium flex items-center gap-2
            ${status.type === 'success' ? 'bg-green-50 border border-green-200 text-green-700' : ''}
            ${status.type === 'error'   ? 'bg-red-50 border border-red-200 text-red-700' : ''}
            ${status.type === 'loading' ? 'bg-orange-50 border border-orange-200 text-orange-700' : ''}`}>
            <span>{status.type === 'success' ? '✅' : status.type === 'error' ? '❌' : '⏳'}</span>
            {status.message}
          </div>
        )}

        {/* Submit */}
        <div className="px-4 sm:px-6 pb-6 sm:pb-8">
          <button
            type="submit"
            disabled={status.type === 'loading'}
            className="w-full bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600
                       text-white font-semibold py-3 sm:py-3.5 rounded-xl transition-all duration-200
                       shadow-md shadow-orange-500/20 hover:shadow-lg hover:shadow-orange-500/30
                       disabled:opacity-60 disabled:cursor-not-allowed active:scale-[0.99] text-xs sm:text-sm"
          >
            {status.type === 'loading' ? 'Submitting…' : 'Register Student →'}
          </button>
        </div>
      </form>
    </div>
  );
}
