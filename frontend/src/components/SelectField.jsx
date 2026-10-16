export default function SelectField({ id, label, options, error, ...selectProps }) {
  return (
    <div>
      <label htmlFor={id} className="mb-1 block font-medium text-leaf-900">
        {label}
      </label>
      <select
        id={id}
        name={id}
        aria-invalid={Boolean(error)}
        className="min-h-12 w-full rounded-lg border border-cream-dark bg-white px-3 py-2 focus:border-leaf-600 focus:outline-none focus:ring-2 focus:ring-leaf-500/40"
        {...selectProps}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      {error && <p className="mt-1 text-sm text-red-700">{error}</p>}
    </div>
  )
}