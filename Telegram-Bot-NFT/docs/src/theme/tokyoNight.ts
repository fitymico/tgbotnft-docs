import type { PrismTheme } from 'prism-react-renderer';

// Tokyo Night theme for Prism
const tokyoNight: PrismTheme = {
  plain: {
    color: '#a9b1d6',
    backgroundColor: 'transparent',
  },
  styles: [
    {
      types: ['comment', 'prolog', 'doctype', 'cdata'],
      style: {
        color: '#565f89',
        fontStyle: 'italic',
      },
    },
    {
      types: ['namespace'],
      style: {
        opacity: 0.7,
      },
    },
    {
      types: ['string', 'attr-value'],
      style: {
        color: '#9ece6a',
      },
    },
    {
      types: ['punctuation', 'operator'],
      style: {
        color: '#89ddff',
      },
    },
    {
      types: ['entity', 'url', 'symbol', 'number', 'boolean', 'variable', 'constant', 'property', 'regex', 'inserted'],
      style: {
        color: '#ff9e64',
      },
    },
    {
      types: ['atrule', 'keyword', 'attr-name', 'selector'],
      style: {
        color: '#bb9af7',
      },
    },
    {
      types: ['function', 'deleted', 'tag'],
      style: {
        color: '#7aa2f7',
      },
    },
    {
      types: ['function-variable'],
      style: {
        color: '#7aa2f7',
      },
    },
    {
      types: ['tag', 'selector', 'keyword'],
      style: {
        color: '#f7768e',
      },
    },
    {
      types: ['builtin', 'class-name'],
      style: {
        color: '#e0af68',
      },
    },
    {
      types: ['char'],
      style: {
        color: '#9ece6a',
      },
    },
    {
      types: ['important'],
      style: {
        fontWeight: 'bold',
      },
    },
    {
      types: ['shebang', 'hashbang'],
      style: {
        color: '#73daca',
      },
    },
  ],
};

export default tokyoNight;
