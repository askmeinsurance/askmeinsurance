import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import type { FormAnswerMap, FormField, FormRequest } from '../../types';

interface PaginatedFormModalProps {
  isOpen: boolean;
  request: FormRequest | null;
  onClose: () => void;
  onSubmit: (formId: string, answers: FormAnswerMap) => void;
}

function getInitialAnswers(request: FormRequest | null): FormAnswerMap {
  if (!request) return {};
  const initial: FormAnswerMap = {};
  request.pages.forEach((page) => {
    page.fields.forEach((field) => {
      if (field.type === 'checkbox') {
        initial[field.id] = false;
        return;
      }
      initial[field.id] = '';
    });
  });
  return initial;
}

function isFilled(value: FormAnswerMap[string]) {
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === 'boolean') return value;
  return String(value ?? '').trim().length > 0;
}

function fieldIsValid(field: FormField, answers: FormAnswerMap) {
  if (!field.required) return true;
  return isFilled(answers[field.id]);
}

export function PaginatedFormModal({ isOpen, request, onClose, onSubmit }: PaginatedFormModalProps) {
  const [pageIndex, setPageIndex] = useState(0);
  const [answers, setAnswers] = useState<FormAnswerMap>(() => getInitialAnswers(request));

  useEffect(() => {
    if (!isOpen) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        onClose();
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !request) return null;
  const formRequest = request;

  const activePage = formRequest.pages[pageIndex];
  const isFirstPage = pageIndex === 0;
  const isLastPage = pageIndex === formRequest.pages.length - 1;
  const canContinue = activePage.fields.every((field) => fieldIsValid(field, answers));

  function updateAnswer(fieldId: string, value: FormAnswerMap[string]) {
    setAnswers((prev) => ({ ...prev, [fieldId]: value }));
  }

  function handleNext() {
    if (!canContinue || isLastPage) return;
    setPageIndex((prev) => prev + 1);
  }

  function handleBack() {
    if (isFirstPage) return;
    setPageIndex((prev) => prev - 1);
  }

  function handleSubmit() {
    if (!canContinue) return;
    onSubmit(formRequest.id, answers);
  }

  function renderField(field: FormField) {
    const value = answers[field.id];
    const invalid = field.required && !fieldIsValid(field, answers);
    const commonLabel = (
      <label className="mb-1.5 block text-sm font-medium text-slate-800" htmlFor={field.id}>
        {field.label}
        {field.required && <span className="ml-1 text-rose-600">*</span>}
      </label>
    );

    if (field.type === 'textarea') {
      return (
        <div key={field.id}>
          {commonLabel}
          <textarea
            id={field.id}
            rows={4}
            value={String(value ?? '')}
            onChange={(event) => updateAnswer(field.id, event.target.value)}
            placeholder={field.placeholder}
            className={`w-full rounded-xl border bg-white px-3 py-2.5 text-sm outline-none transition ${
              invalid ? 'border-rose-400' : 'border-slate-300 focus:border-cyan-500'
            }`}
          />
        </div>
      );
    }

    if (field.type === 'select') {
      return (
        <div key={field.id}>
          {commonLabel}
          <select
            id={field.id}
            value={String(value ?? '')}
            onChange={(event) => updateAnswer(field.id, event.target.value)}
            className={`w-full rounded-xl border bg-white px-3 py-2.5 text-sm outline-none transition ${
              invalid ? 'border-rose-400' : 'border-slate-300 focus:border-cyan-500'
            }`}
          >
            <option value="">Select an option</option>
            {(field.options ?? []).map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      );
    }

    if (field.type === 'radio') {
      return (
        <div key={field.id}>
          {commonLabel}
          <div className="grid gap-2">
            {(field.options ?? []).map((option) => (
              <label
                key={option.value}
                className="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
              >
                <input
                  type="radio"
                  name={field.id}
                  checked={value === option.value}
                  onChange={() => updateAnswer(field.id, option.value)}
                />
                <span>{option.label}</span>
              </label>
            ))}
          </div>
        </div>
      );
    }

    if (field.type === 'checkbox') {
      return (
        <div key={field.id} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
          <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-800">
            <input
              id={field.id}
              type="checkbox"
              checked={Boolean(value)}
              onChange={(event) => updateAnswer(field.id, event.target.checked)}
            />
            <span>
              {field.label}
              {field.required && <span className="ml-1 text-rose-600">*</span>}
            </span>
          </label>
        </div>
      );
    }

    return (
      <div key={field.id}>
        {commonLabel}
        <input
          id={field.id}
          type="text"
          value={String(value ?? '')}
          onChange={(event) => updateAnswer(field.id, event.target.value)}
          placeholder={field.placeholder}
          className={`w-full rounded-xl border bg-white px-3 py-2.5 text-sm outline-none transition ${
            invalid ? 'border-rose-400' : 'border-slate-300 focus:border-cyan-500'
          }`}
        />
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-4" onClick={onClose}>
      <div
        className="w-full max-w-2xl overflow-hidden rounded-2xl border border-cyan-200/70 bg-[linear-gradient(140deg,#f7fdff_0%,#f4f6ff_45%,#fffaf4_100%)] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between border-b border-slate-200/80 px-6 py-4">
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-cyan-700">Input Required</p>
            <h2 className="mt-1 text-xl font-semibold text-slate-900">{formRequest.title}</h2>
            {formRequest.description && <p className="mt-1 text-sm text-slate-600">{formRequest.description}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-slate-300 bg-white p-1.5 text-slate-600 hover:bg-slate-100"
            aria-label="Close form"
          >
            <X size={16} />
          </button>
        </div>

        <div className="px-6 pt-4">
          <div className="mb-4 flex items-center gap-2">
            {formRequest.pages.map((page, index) => (
              <div key={page.id} className="flex flex-1 items-center gap-2">
                <div
                  className={`h-1.5 flex-1 rounded-full ${
                    index <= pageIndex ? 'bg-cyan-500' : 'bg-slate-200'
                  }`}
                />
              </div>
            ))}
          </div>
          <h3 className="text-base font-semibold text-slate-900">{activePage.title}</h3>
          {activePage.description && <p className="mt-1 text-sm text-slate-600">{activePage.description}</p>}
        </div>

        <div className="max-h-[52vh] space-y-4 overflow-y-auto px-6 py-4">
          {activePage.fields.map((field) => renderField(field))}
        </div>

        <div className="flex items-center justify-between border-t border-slate-200/80 bg-white/65 px-6 py-4">
          <button
            type="button"
            onClick={handleBack}
            disabled={isFirstPage}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Back
          </button>
          <div className="text-xs text-slate-500">
            Page {pageIndex + 1} of {formRequest.pages.length}
          </div>
          {!isLastPage ? (
            <button
              type="button"
              onClick={handleNext}
              disabled={!canContinue}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              Next
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSubmit}
              disabled={!canContinue}
              className="rounded-lg bg-cyan-600 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              {formRequest.submitLabel ?? 'Submit'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
