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

  url: 'https://dimopster.github.io',
  baseUrl: '/Telegram-Bot-NFT/',

  organizationName: 'Dimopster',
  projectName: 'Telegram-Bot-NFT',
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
          editUrl: 'https://github.com/Dimopster/Telegram-Bot-NFT/tree/main/docs/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    image: 'img/docusaurus-social-card.jpg',
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
          href: 'https://github.com/Dimopster/Telegram-Bot-NFT',
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
