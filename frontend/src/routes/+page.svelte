<script>
  import { goto } from "$app/navigation";
  import { onMount } from "svelte";
  onMount(() => goto("/receipts", { replaceState: true }));
</script>
