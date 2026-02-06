import tokyoNight from './src/theme/tokyoNight';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'Telegram Bot NFT',
  tagline: 'Автоматизация работы с NFT-подарками в Telegram',
  favicon: 'img/logo.webp',

  future: {
    v4: true,
  },

  url: 'https://fitymico.github.io',
  baseUrl: '/tgbotnft-docs/',

  organizationName: 'fitymico',
  projectName: 'tgbotnft-docs',
  trailingSlash: false,

  onBrokenLinks: 'throw',

  i18n: {
    defaultLocale: 'ru',
    locales: ['ru'],
  },

  headTags: [
    {
      tagName: 'link',
      attributes: {
        rel: 'preconnect',
        href: 'https://fonts.googleapis.com',
      },
    },
    {
      tagName: 'link',
      attributes: {
        rel: 'preconnect',
        href: 'https://fonts.gstatic.com',
        crossorigin: 'anonymous',
      },
    },
    {
      tagName: 'link',
      attributes: {
        rel: 'stylesheet',
        href: 'https://fonts.googleapis.com/css2?family=Montserrat+Alternates:wght@400;500;600;700;800&display=swap',
      },
    },
  ],

  markdown: {
    mermaid: true,
  },

  themes: ['@docusaurus/theme-mermaid'],

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          editUrl: 'https://github.com/fitymico/tgbotnft-docs/tree/main/',
          routeBasePath: '/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    image: 'img/social-card.jpg',
    colorMode: {
      defaultMode: 'dark',
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'Telegram Bot NFT',
      logo: {
        alt: 'Telegram Bot NFT Logo',
        src: 'img/logo.webp',
      },
      items: [
        {
          to: '/purchase',
          label: 'Купить',
          position: 'left',
        },
        {
          to: '/getting-started/quick-start',
          label: 'Установка',
          position: 'left',
        },
        {
          href: 'https://github.com/fitymico/tgbotnft',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: undefined, // Footer disabled - using custom copyright on homepage
    prism: {
      theme: tokyoNight,
      darkTheme: tokyoNight,
      additionalLanguages: ['bash', 'diff', 'json'],
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
