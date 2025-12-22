# Quick setup commands

## In Discord, as a moderator with Manage Server:

Set mod channel:

`f.sheet setmod #mod-alerts`

Set channels that contain the sheet messages:

`f.sheet setmodrole @roles`

Set roles that can user the sheetwatch commands aside from the admin ones

`f.sheet settracked #approved-sheets #approved-sheets-2`

Discover existing sheets:

`f.sheet rescan`

Approve a baseline for a doc:

`f.sheet approve https://docs.google.com/document/d/<DOC_ID>/edit`




# 📄 SheetWatch – Moderator Commands

**Prefix:** `f.`
**Who can use these:** Server moderators (Manage Server permission)

SheetWatch watches approved Google Docs character sheets and alerts mods if someone edits them without approval.

---

## 🔧 Setup (one-time)

### `f.sheet setmod #channel`

Sets where SheetWatch posts alerts when a sheet is changed.

```
f.sheet setmod #mod-alerts
```

---

## 🔧 Setup (one-time)

### `f.sheet setmodrole @roles`

Set roles that can user the sheetwatch commands aside from the admin ones

```
f.sheet setmodrole @sheetmod
```

---

### `f.sheet settracked #channel1 #channel2 ...`

Marks channels that contain **approved character sheets**.

Any message in these channels that mentions a user and links a Google Doc is treated as approved.

```
f.sheet settracked #approved-sheets
```

---

## 🚨 Checking Sheets

### `f.sheet check <google doc link>`

Manually check a sheet **right now**.

* No change → nothing happens
* Changed → alert appears in the mod channel

```
f.sheet check https://docs.google.com/document/d/XXXX/edit
```

---

### `f.sheet diff <google doc link>`

Show **what changed** without opening an alert.

Useful for quickly reviewing edits.

```
f.sheet diff https://docs.google.com/document/d/XXXX/edit
```

---

## 🧪 Testing / Debugging

### `f.sheet dump <google doc link>`

Save the cleaned version of the sheet (the text SheetWatch checks) to disk.

This is for admins/devs only.

```
f.sheet dump https://docs.google.com/document/d/XXXX/edit
```

---

## 📜 History

### `f.sheet audit <google doc link>`

Show recent history for a sheet:

* approvals
* detected edits
* resolutions

```
f.sheet audit https://docs.google.com/document/d/XXXX/edit
```

---

## ⏱️ Automatic Checks (No Command Needed)

* Sheets are automatically re-checked about **every 12 hours**
* If a sheet is edited:

  * Mods get an alert
  * Changes are highlighted in red/green
* If the sheet is reverted:

  * The alert resolves automatically

---

## 📝 Notes for Mods

* Formatting, colors, images **do not matter**
* Reordering sections is allowed
* Changing text, adding/removing sections **does trigger alerts**
* All sheets must be **public view** Google Docs

---

If you want, I can also:

* turn this into a **Discord embed**
* write a **player-facing explanation** (“why did my sheet get flagged?”)
* add a **one-page mod cheat sheet** with screenshots
