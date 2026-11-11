import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import App from '../App'

describe('App', () => {
  it('renders the page title', () => {
    render(<App />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Study Guide Generator')
  })

  it('renders the upload area', () => {
    render(<App />)
    expect(screen.getByRole('region', { name: /upload area/i })).toBeInTheDocument()
  })
})

