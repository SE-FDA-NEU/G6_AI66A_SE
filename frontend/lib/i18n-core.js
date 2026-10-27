import existingMessages from '../locales/messages.json';
import uxMessages from '../locales/ux.json';
import guideMessages from '../locales/guides.json';
import historyMessages from '../locales/history.json';
const messages = { ...Object.fromEntries([...uxMessages, ...guideMessages, ...historyMessages].map(([vi, en]) => [vi, { vi, en }])), ...existingMessages };

export const LOCALE_COOKIE = 'documind_language';
export function readLocale(cookie = '') {
  return /(?:^|;\s*)documind_language=en(?:;|$)/.test(cookie) ? 'en' : 'vi';
}

const aliases = new Map();
for (const [key, pair] of Object.entries(messages)) {
  aliases.set(key, key);
  aliases.set(pair.vi, key);
  aliases.set(pair.en, key);
}
const patterns = [];
for (const [key, pair] of Object.entries(messages)) {
  if (!/\{\d+\}/.test(key)) continue;
  for (const text of new Set([key, pair.vi, pair.en])) {
    const indexes = [];
    const escaped = text.split(/(\{\d+\})/).map(part => {
      if (/^\{\d+\}$/.test(part)) { indexes.push(Number(part.slice(1, -1))); return '(.+?)'; }
      return part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }).join('');
    patterns.push({ key, indexes, regex: new RegExp(`^${escaped}$`, 's') });
  }
}

export function translate(locale, message, ...values) {
  if (typeof message !== 'string' || !message) return message;
  let key = messages[message] ? message : aliases.get(message);
  if (!key && !values.length) {
    for (const pattern of patterns) {
      const match = message.match(pattern.regex);
      if (match) {
        key = pattern.key;
        values = [];
        pattern.indexes.forEach((index, order) => { values[index] = match[order + 1]; });
        break;
      }
    }
  }
  const result = messages[key]?.[locale === 'en' ? 'en' : 'vi'] ?? message;
  return values.length ? result.replace(/\{(\d+)\}/g, (token, index) => values[index] == null ? '' : String(values[index])) : result;
}

export function isLocalizedMessage(message) { return typeof message === "string" && (aliases.has(message) || patterns.some(pattern => pattern.regex.test(message))); }
