/**
 * Client-side Pathbuilder 2e utilities.
 *
 * The Pathbuilder `json.php` endpoint is behind Cloudflare bot protection that
 * blocks server-side HTTP clients.  Fetching from the browser (a real
 * user-agent) passes the challenge automatically, so we do the fetch here and
 * POST the raw response to the Grug API.
 */

const PATHBUILDER_URL = 'https://pathbuilder2e.com/json.php';

/**
 * Fetch a Pathbuilder character's JSON directly from the browser.
 *
 * Returns the full raw response `{ success: boolean, build: {...} }` which
 * should be passed as `pathbuilder_data` to the Grug API endpoints so the
 * server can normalise it without making an outbound HTTP request.
 *
 * @throws {Error} If the request fails or the server returns success=false.
 */
export async function fetchPathbuilderClientSide(pbId: number): Promise<object> {
  let res: Response;
  try {
    res = await fetch(`${PATHBUILDER_URL}?id=${pbId}`);
  } catch (err) {
    throw new Error(`Could not reach Pathbuilder: ${err}`);
  }
  if (!res.ok) {
    throw new Error(`Pathbuilder returned HTTP ${res.status}`);
  }
  const data = await res.json();
  if (!data.success) {
    throw new Error('Pathbuilder returned success=false — character not found or not shared');
  }
  return data;
}
