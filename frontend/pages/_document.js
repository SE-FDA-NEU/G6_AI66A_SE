import NextDocument, { Html, Head, Main, NextScript } from 'next/document';
import { readLocale } from '../lib/i18n-core';
export default class Document extends NextDocument {
  static async getInitialProps(context) {
    const props = await NextDocument.getInitialProps(context);
    return { ...props, locale: readLocale(context.req?.headers.cookie) };
  }
  render() {
    return <Html lang={this.props.locale} data-scroll-behavior="smooth"><Head /><body><Main /><NextScript /></body></Html>;
  }
}
