<script>
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import {
    listCategories,
    createCategory,
    updateCategory,
    deleteCategory,
  } from "$lib/api";
  import { currentUser } from "$lib/auth";

  let categories = $state([]);
  let error = $state("");

  // New-category form
  let newName = $state("");
  let creating = $state(false);

  // Inline edit state (which row is open + its draft value).
  let editId = $state(null);
  let editValue = $state("");

  const canManage = $derived(
    $currentUser?.role === "admin" || $currentUser?.role === "superadmin",
  );

  async function refresh() {
    try {
      categories = await listCategories();
    } catch (e) {
      error = e.message;
    }
  }

  onMount(async () => {
    // Page-level guard: admins only (the shell already ensured auth).
    if ($currentUser && !canManage) {
      goto("/");
      return;
    }
    await refresh();
  });

  async function onCreate(e) {
    e.preventDefault();
    error = "";
    const name = newName.trim();
    if (!name) return;
    creating = true;
    try {
      await createCategory(name);
      newName = "";
      await refresh();
    } catch (err) {
      error = err.message;
    } finally {
      creating = false;
    }
  }

  function startEdit(c) {
    editId = c.id;
    editValue = c.name;
    error = "";
  }

  function cancelEdit() {
    editId = null;
    editValue = "";
  }

  async function saveEdit(c) {
    const name = editValue.trim();
    if (!name) return;
    if (name === c.name) {
      cancelEdit();
      return;
    }
    error = "";
    try {
      await updateCategory(c.id, name);
      cancelEdit();
      await refresh();
    } catch (err) {
      error = err.message;
    }
  }

  async function onDelete(c) {
    if (!confirm(`Delete category "${c.name}"? Existing receipts keep their label.`)) return;
    error = "";
    try {
      await deleteCategory(c.id);
      await refresh();
    } catch (err) {
      error = err.message;
    }
  }
</script>

<div class="max-w-2xl mx-auto px-4 py-8 space-y-6">
  <h1 class="text-2xl font-semibold">Categories</h1>
  <p class="text-sm text-slate-500">
    Group receipts by type — e.g. supermarket, fuel station, restaurant. These
    options appear when reviewing a receipt and as filters on the receipts list.
  </p>

  {#if error}
    <div class="bg-red-50 text-red-700 border border-red-200 rounded-lg p-3 text-sm">
      {error}
    </div>
  {/if}

  <!-- Add category -->
  <section class="bg-white rounded-xl shadow-sm p-5">
    <h2 class="font-semibold mb-3">Add a category</h2>
    <form onsubmit={onCreate} class="flex gap-3">
      <input
        bind:value={newName}
        placeholder="e.g. supermarket"
        maxlength="64"
        class="flex-1 rounded-lg border border-slate-300 p-2 text-sm"
      />
      <button
        type="submit"
        disabled={creating || !newName.trim()}
        class="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm"
      >
        {creating ? "Adding…" : "Add"}
      </button>
    </form>
  </section>

  <!-- List -->
  <section class="bg-white rounded-xl shadow-sm p-5">
    <h2 class="font-semibold mb-3">All categories ({categories.length})</h2>
    {#if categories.length === 0}
      <p class="text-sm text-slate-500">No categories yet — add one above.</p>
    {:else}
      <ul class="divide-y text-sm">
        {#each categories as c (c.id)}
          <li class="flex items-center gap-2 py-2">
            {#if editId === c.id}
              <input
                bind:value={editValue}
                maxlength="64"
                class="flex-1 rounded-lg border border-slate-300 p-2"
              />
              <button
                onclick={() => saveEdit(c)}
                class="text-blue-600 hover:underline text-xs"
              >
                save
              </button>
              <button onclick={cancelEdit} class="text-slate-500 hover:underline text-xs">
                cancel
              </button>
            {:else}
              <span class="flex-1 capitalize">{c.name}</span>
              <button
                onclick={() => startEdit(c)}
                class="text-blue-600 hover:underline text-xs"
              >
                edit
              </button>
              <button
                onclick={() => onDelete(c)}
                class="text-red-600 hover:underline text-xs"
              >
                delete
              </button>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}
  </section>
</div>
