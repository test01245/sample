import './App.css'

const tiles = [
  {
    key: 'python',
    title: 'Python',
    desc: 'Popular for scripting, data science, and automation. Clean syntax and rich ecosystem.',
    icon: (
      <svg width="120" height="120" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 2c2.8 0 5 2.2 5 5v1.5h-6.5c-1.1 0-2 .9-2 2V14H7c-2.8 0-5-2.2-5-5 0-2.7 2.2-5 5-5h5z" fill="#3776AB"/>
        <circle cx="9.5" cy="5.5" r=".9" fill="#fff"/>
        <path d="M12 22c-2.8 0-5-2.2-5-5v-1.5h6.5c1.1 0 2-.9 2-2V10H17c2.8 0 5 2.2 5 5 0 2.7-2.2 5-5 5h-5z" fill="#FFD343"/>
        <circle cx="14.5" cy="18.5" r=".9" fill="#2b2b2b"/>
      </svg>
    ),
  },
  {
    key: 'javascript',
    title: 'JavaScript',
    desc: 'The language of the web—build interactive UIs, servers, and everything in between.',
    icon: (
      <svg width="120" height="120" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <rect x="3" y="3" width="18" height="18" rx="2" fill="#F7DF1E"/>
        <path d="M11 8h2v7.5c0 1.8-1.2 2.6-2.7 2.6-.7 0-1.4-.2-1.9-.5l.6-1.7c.4.2.8.3 1.2.3.5 0 .8-.2.8-.8V8zM16.5 16c.5.5 1.1.8 1.8.8.7 0 1.2-.3 1.2-.9 0-.6-.5-.8-1.3-1.2l-.4-.2c-1.2-.5-2-1.2-2-2.7 0-1.3 1-2.3 2.6-2.3 1.1 0 1.9.4 2.4 1l-1.3 1c-.3-.4-.7-.6-1.1-.6-.5 0-.9.3-.9.8 0 .6.4.8 1.3 1.2l.4.2c1.3.6 2.1 1.3 2.1 2.7 0 1.5-1.2 2.3-2.8 2.3-1.3 0-2.2-.4-2.8-1l1.1-1.4z" fill="#2b2b2b"/>
      </svg>
    ),
  },
  {
    key: 'java',
    title: 'Java',
    desc: 'Robust, portable, and widely used for enterprise and Android development.',
    icon: (
      <svg width="120" height="120" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 4c2 2-.5 3-.5 4.5S14 10.5 14 12c0 1.5-3 2-3 3.5S14 18 14 20" stroke="#f97316" strokeWidth="1.5" fill="none"/>
        <path d="M6 18c2 1 10 1 12 0M8 20c3 1 5 1 8 0" stroke="#1f2937" strokeWidth="1.5" fill="none"/>
        <circle cx="12" cy="4" r=".7" fill="#2563eb"/>
      </svg>
    ),
  },
  {
    key: 'csharp',
    title: 'C#',
    desc: 'Modern, object-oriented language for .NET apps, games (Unity), and services.',
    icon: (
      <svg width="120" height="120" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <polygon points="12,2 22,8 22,16 12,22 2,16 2,8" fill="#9C27B0"/>
        <text x="12" y="14" textAnchor="middle" fontSize="8" fill="#fff" fontFamily="monospace">C#</text>
      </svg>
    ),
  },
  {
    key: 'go',
    title: 'Go',
    desc: 'Fast, statically typed, great for concurrency and cloud-native services.',
    icon: (
      <svg width="120" height="120" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <rect x="3" y="6" width="18" height="12" rx="6" fill="#00ADD8"/>
        <circle cx="9" cy="12" r="1.2" fill="#fff"/>
        <circle cx="15" cy="12" r="1.2" fill="#fff"/>
      </svg>
    ),
  },
  {
    key: 'ruby',
    title: 'Ruby',
    desc: 'Elegant and expressive. Great for rapid web development with Rails.',
    icon: (
      <svg width="120" height="120" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <polygon points="12,3 20,8 16,21 8,21 4,8" fill="#CC342D"/>
        <polygon points="12,3 16,21 8,21" fill="#e66" opacity=".5"/>
      </svg>
    ),
  },
]

export default function HomeGrid() {
  return (
    <div className="container">
      <div className="grid-3">
        {tiles.map(t => (
          <div key={t.key} className="tile">
            <div className="tile-icon">{t.icon}</div>
            <h3 className="tile-title">{t.title}</h3>
            <p className="tile-desc">{t.desc}</p>
            <a className="tile-link" href="#">Learn About This Language →</a>
          </div>
        ))}
      </div>
    </div>
  )
}
