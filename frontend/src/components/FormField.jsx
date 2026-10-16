export default function FormField({ id, label, error, ...inputProps }) {
  return (
    <div>
      <label htmlFor={id} className="mb-1 block font-medium text-leaf-900">
        {label}
      </label>
      <input
        id={id}
        name={id}
        aria-invalid={Boolean(error)}
        className="min-h-12 w-full rounded-lg border border-cream-dark bg-white px-3 py-2 focus:border-leaf-600 focus:outline-none focus:ring-2 focus:ring-leaf-500/40"
        {...inputProps}
      />
      {error && <p className="mt-1 text-sm text-red-700">{error}</p>}
    </div>
  )
}