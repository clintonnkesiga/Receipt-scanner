<script>
  import { onMount } from "svelte";
  import {
    listCategories,
    createCategory,
    updateCategory,
    deleteCategory,
  } from "$lib/api";
  import { currentUser } from "$lib/auth";
  import { toasts } from "$lib/toast.js";
  import ConfirmDialog from "$lib/components/ConfirmDialog.svelte";

  let categories = $state([]);

  // New-category form
  let newName = $state("");
  let creating = $state(false);

  // Inline edit state (which row is open + its draft value).
  let editId = $state(null);
  let editValue = $state("");

  // Admins can manage the shared/system defaults (owner_id === null);
  // everyone manages categories they own.
  const isAdmin = $derived(
    $currentUser?.role === "admin" || $currentUser?.role === "superadmin",
  );
  const me = $derived($currentUser?.id);

  function editable(c) {
    return c.owner_id === me || (c.owner_id == null && isAdmin);
  }

  async function refresh() {
    try {
      categories = await listCategories();
    } catch (e) {
      toasts.error(
        e instanceof Error ? e.message : "Could not load categories",
      );
    }
  }

  onMount(async () => {
    await refresh();
  });

  async function onCreate(e) {
    e.preventDefault();
    const name = newName.trim();
    if (!name) return;
    creating = true;
    try {
      await createCategory(name);
      newName = "";
      await refresh();
      toasts.success(`Category "${name}" added`);
    } catch (err) {
      toasts.error(
        err instanceof Error ? err.message : "Could not create category",
      );
    } finally {
      creating = false;
    }
  }

  function startEdit(c) {
    editId = c.id;
    editValue = c.name;
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
    try {
      await updateCategory(c.id, name);
      cancelEdit();
      await refresh();
      toasts.success(`Category renamed to "${name}"`);
    } catch (err) {
      toasts.error(
        err instanceof Error ? err.message : "Could not update category",
      );
    }
  }

  // Category pending deletion (drives the confirm dialog); null = closed.
  let pendingDelete = $state(null);
  let deleting = $state(false);

  async function confirmDelete() {
    if (!pendingDelete) return;
    const c = pendingDelete;
    deleting = true;
    try {
      await deleteCategory(c.id);
      pendingDelete = null;
      await refresh();
      toasts.success(`Category "${c.name}" deleted`);
    } catch (err) {
      toasts.error(
        err instanceof Error ? err.message : "Could not delete category",
      );
    } finally {
      deleting = false;
    }
  }
</script>

<div class="w-full px-4 sm:px-6 py-6 sm:py-8 space-y-6">
  <h1 class="text-2xl font-semibold">Categories</h1>
  <p class="text-sm text-slate-500">
    Group receipts by type — e.g. supermarket, fuel station, restaurant. These
    options appear when reviewing a receipt and as filters on the receipts list.
    You see the <span class="font-medium">shared</span> defaults plus any you add,
    and you can manage your own.
  </p>

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
                type="button"
                onclick={() => saveEdit(c)}
                class="text-blue-600 hover:underline text-xs"
              >
                save
              </button>
              <button
                type="button"
                onclick={cancelEdit}
                class="text-slate-500 hover:underline text-xs"
              >
                cancel
              </button>
            {:else}
              <span class="flex-1 capitalize">{c.name}</span>
              {#if c.owner_id == null}
                <span
                  class="text-[10px] uppercase tracking-wide rounded-full bg-slate-100 text-slate-500 px-2 py-0.5"
                >
                  shared
                </span>
              {/if}
              {#if editable(c)}
                <button
                  onclick={() => startEdit(c)}
                  class="text-blue-600 hover:underline text-xs"
                >
                  edit
                </button>
                <button
                  onclick={() => (pendingDelete = c)}
                  class="text-red-600 hover:underline text-xs"
                >
                  delete
                </button>
              {/if}
            {/if}
          </li>
        {/each}
      </ul>
    {/if}
  </section>
</div>

<!-- Delete confirmation -->
<ConfirmDialog
  open={pendingDelete != null}
  danger
  busy={deleting}
  title={pendingDelete ? `Delete “${pendingDelete.name}”?` : ""}
  message="Existing receipts keep their label — only the category option is removed."
  confirmLabel={deleting ? "Deleting…" : "Delete"}
  onconfirm={confirmDelete}
  oncancel={() => (pendingDelete = null)}
/>
