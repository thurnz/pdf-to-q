export default function App() {
  return (
    <main className="min-h-screen flex flex-col items-center px-4 py-16 sm:py-24">
      {/* ── Header ───────────────────────────────────────── */}
      <header className="w-full max-w-2xl mb-12">
        <h1
          className="text-4xl sm:text-5xl font-bold leading-tight mb-4"
          style={{ fontFamily: 'var(--font-display)', color: 'var(--color-heading)' }}
        >
          Study Guide Generator
        </h1>
        <p className="text-lg leading-relaxed max-w-prose" style={{ color: 'var(--color-muted)' }}>
          Upload a PDF — lecture notes, a chapter, a paper — and get a focused question-and-answer
          study guide back as a PDF you can print or annotate.
        </p>
      </header>

      {/* ── Upload zone placeholder ───────────────────────── */}
      <section
        aria-label="Upload area"
        className="w-full max-w-2xl rounded-xl border-2 border-dashed flex flex-col items-center justify-center gap-3 py-16 px-6 text-center"
        style={{
          borderColor: 'var(--color-border)',
          backgroundColor: 'var(--color-zone-bg)',
        }}
      >
        {/* Cloud-upload icon (inline SVG, no icon lib needed) */}
        <svg
          aria-hidden="true"
          width="40"
          height="40"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{ color: 'var(--color-primary)' }}
        >
          <polyline points="16 16 12 12 8 16" />
          <line x1="12" y1="12" x2="12" y2="21" />
          <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3" />
        </svg>

        <p className="text-base font-medium" style={{ color: 'var(--color-heading)' }}>
          Drop your PDF here
        </p>
        <p className="text-sm" style={{ color: 'var(--color-muted)' }}>
          or{' '}
          <button
            type="button"
            className="underline underline-offset-2 cursor-pointer"
            style={{ color: 'var(--color-primary)' }}
          >
            choose a file
          </button>
        </p>
        <p className="text-xs mt-1" style={{ color: 'var(--color-muted)' }}>
          PDF only · up to 20 MB · 200 pages
        </p>
      </section>
    </main>
  )
}
