# Admin Panel Editing via Browser Harness

Patterns for editing content management panels (Backpack/Laravel admin, TinyMCE editors) via browser automation.

## RealisticAsia Admin Panel (`admin.realisticasia.com`)

### Session Auth Required
No API endpoint for session creation. Must log in via UI:
1. Navigate to `https://admin.realisticasia.com/user/login`
2. Form fields: `#form_item_email`, `#form_item_password`
3. Submit via JS: `document.querySelector("button[type=submit]").click()`

### Navigation Patterns
- Dashboard: `/dashboard`
- Tour list: `/travel/tour`
- **Direct tour edit**: `/travel/tour/{id}` (ALWAYS use direct URL — list pages timeout)
- Other resources follow pattern: `/travel/{resource}/{id}`

### Tab Structure (Ant Design Tabs)
Tour edit page uses `.ant-tabs-tab` for tab switching:
```javascript
// Click tab by text content
var tabs = Array.from(document.querySelectorAll('.ant-tabs-tab'));
var target = tabs.find(t => t.textContent.trim() === 'Itinerary');
if (target) target.click();
```

Tabs on tour edit: Details, Itinerary, Photos, What's included, Rooms & Traveller Types, Pricing & Availability, Properties

### Form Fields (TinyMCE Editors)
Rich text fields rendered as TinyMCE iframes with `title="Rich Text Area"`.

**Read content:**
```javascript
Array.from(document.querySelectorAll('iframe')).map(f => {
  try { return f.contentDocument?.body?.innerText || "" } 
  catch(e) { return "" }
})
```

**Update content:**
```javascript
var frames = Array.from(document.querySelectorAll('iframe'));
var count = 0;
frames.forEach(f => {
  try {
    var bd = f.contentDocument.body;
    if (bd) { bd.innerHTML = "<p>new content</p>"; count++ }
  } catch(e) {}
});
count; // returns number updated
```

### Standard Input Fields
Regular form inputs (name, slug, code, duration, price):
- Located near label elements in `.form-group` containers
- Values accessible via `document.querySelectorAll('input[value]')`
- Use JS to set + dispatch events for framework reactivity

### Save/Submit
Primary save button: `.ant-btn-primary` (Ant Design). **Fallback**: if selector fails, find by text content — the page may render Save without primary class when in certain tabs.
```javascript
var btn = document.querySelector('.ant-btn-primary');
if (!btn) {
  btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === 'Save');
}
if (btn) btn.click();
```

### Deleting Items via UI
When API delete endpoints don't exist or fail, use the admin UI to remove records. Ant Design uses `.ant-btn-danger` for destructive actions.

**Identify duplicates by counting text occurrences:**
```javascript
// Count Day X patterns in body text to find duplicates
var body = document.body.innerText;
var matches = body.match(/Day \d+/g);
// Use collections.Counter (Python side) or manual grouping to find which days appear >1 time
```

**Delete by index (work bottom-up so indices don't shift):**
```javascript
// Get all delete buttons
var btns = document.querySelectorAll('.ant-btn-danger');
// Delete the last duplicate first, then work upward
btns[6].click(); // click last
wait(1);
btns[4].click(); // click earlier one (after re-indexing or use fresh query)
```

**No confirmation modal**: RealisticAsia deletes immediately without a confirm dialog — no need to look for `.ant-modal-confirm`.

## General Patterns

### Detecting Editor Type
```javascript
// Check for TinyMCE
document.querySelectorAll('.tox-tinymce').length > 0

// Check for CKEditor  
document.querySelectorAll('.ck-editor').length > 0

// Check for iframes (generic rich editors)
document.querySelectorAll('iframe[title*="Rich"]').length > 0
```

### Vue/React Form Reactivity
Setting `input.value` alone doesn't trigger watchers. Must dispatch:
```javascript
el.value = "new value";
el.dispatchEvent(new Event("input", {bubbles:true}));
el.dispatchEvent(new Event("change", {bubbles:true}));
```

### Avoid List Page Timeouts
List pages with pagination/lazy-load frequently exceed harness timeout (30-120s). Always navigate directly to the resource URL:
- ❌ Navigate to `/tours` → find row → click edit
- ✅ Navigate to `/travel/tour/555` directly
