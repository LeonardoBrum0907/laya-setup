// Node-only helpers: load the shared schema and append decisions to a JSONL log.

import { appendFileSync, mkdirSync, readFileSync } from 'node:fs';
import { dirname } from 'node:path';
import type { Questions } from './laya-client.ts';
import type { DecisionLog } from './perception.ts';

export function loadQuestions(schemaPath: string): Questions {
  const schema = JSON.parse(readFileSync(schemaPath, 'utf8')) as { questions: Questions };
  return schema.questions;
}

export function jsonlLogger(path: string): (entry: DecisionLog) => void {
  mkdirSync(dirname(path), { recursive: true });
  return (entry) => appendFileSync(path, `${JSON.stringify(entry)}\n`, 'utf8');
}
