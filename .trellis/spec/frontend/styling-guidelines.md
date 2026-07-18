# Frontend Styling Guidelines

## Convention: Use TailwindCSS for Styling

**What**: All frontend styling must be implemented using TailwindCSS utility classes.

**Why**: To maintain a consistent design system, reduce CSS bundle size, and avoid the specificity and maintenance issues of traditional custom CSS. Writing traditional custom CSS (e.g., standard `.css`, `.scss`, or styled-components) should be avoided as much as possible unless absolutely necessary for specific overrides that Tailwind cannot handle.

**Example**:
```html
<!-- Good: Using TailwindCSS utilities -->
<button class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded">
  Submit
</button>

<!-- Bad: Using custom traditional CSS classes -->
<button class="btn-primary">
  Submit
</button>
```

**Related**:
- [Tailwind CSS Documentation](https://tailwindcss.com/docs)
