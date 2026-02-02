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

  url: 'https://seventyzero.github.io',
  baseUrl: '/tgbotnft-docs/',

  organizationName: 'seventyzero',
  projectName: 'tgbotnft-docs',
  trailingSlash: false,

  onBrokenLinks: 'throw',

  i18n: {
    defaultLocale: 'ru',
    locales: ['ru'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          editUrl: 'https://github.com/seventyzero/tgbotnft-docs/tree/main/',
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
          type: 'docSidebar',
          sidebarId: 'tutorialSidebar',
          position: 'left',
          label: 'Установка',
        },
        {
          href: 'https://github.com/seventyzero/tgbotnft',
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
