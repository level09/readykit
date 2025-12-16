import { defineConfig } from 'vitepress'

export default defineConfig({
  base: '/readykit/',
  title: 'ReadyKit',
  description: 'Production-ready Flask SaaS template with multi-tenant workspaces, Stripe billing, and team collaboration',

  head: [
    ['link', { rel: 'icon', href: '/readykit/favicon.svg' }]
  ],

  themeConfig: {
    logo: '/logo/light.svg',

    nav: [
      { text: 'Guide', link: '/introduction' },
      { text: 'GitHub', link: 'https://github.com/level09/readykit' }
    ],

    sidebar: [
      {
        text: 'Getting Started',
        items: [
          { text: 'Introduction', link: '/introduction' },
          { text: 'Quick Start', link: '/getting-started' }
        ]
      },
      {
        text: 'Core Concepts',
        items: [
          { text: 'Workspaces', link: '/workspaces' },
          { text: 'Billing', link: '/billing' },
          { text: 'Teams', link: '/teams' }
        ]
      },
      {
        text: 'Development',
        items: [
          { text: 'Authentication', link: '/authentication' },
          { text: 'Development Guide', link: '/development' },
          { text: 'AI Agents', link: '/agents' }
        ]
      },
      {
        text: 'Deployment',
        items: [
          { text: 'Overview', link: '/deployment' },
          { text: 'Fly.io', link: '/deployment/fly' },
          { text: 'Railway', link: '/deployment/railway' }
        ]
      }
    ],

    socialLinks: [
      { icon: 'github', link: 'https://github.com/level09/readykit' }
    ],

    footer: {
      message: 'Built with ReadyKit',
      copyright: 'MIT License'
    },

    search: {
      provider: 'local'
    }
  }
})
