"""
history.py — ElevenLabs Conversation History fetcher

Retrieves completed conversation sessions from a deployed ElevenLabs agent
and structures them for downstream analysis. Uses cursor-based pagination
to handle large history volumes.
"""

import httpx
from rich.console import Console

console = Console()

CONVERSATIONS_URL  = "https://api.elevenlabs.io/v1/convai/conversations"
CONVERSATION_URL   = "https://api.elevenlabs.io/v1/convai/conversations/{conversation_id}"


def fetch_conversations(
    agent_id: str,
    api_key: str,
    limit: int = 50,
) -> list[dict]:
    """
    Fetch a list of completed conversation summaries for an agent.

    Args:
        agent_id: ElevenLabs agent ID.
        api_key:  ElevenLabs API key.
        limit:    Maximum number of conversations to retrieve (default 50).

    Returns:
        List of conversation summary dicts.
    """
    headers = {"xi-api-key": api_key}
    conversations = []
    cursor = None

    with httpx.Client(timeout=30.0) as client:
        while len(conversations) < limit:
            page_size = min(100, limit - len(conversations))
            params = {"agent_id": agent_id, "page_size": page_size}
            if cursor:
                params["cursor"] = cursor

            response = client.get(CONVERSATIONS_URL, headers=headers, params=params)

            if response.status_code != 200:
                raise RuntimeError(
                    f"History API error {response.status_code}: {response.text[:200]}"
                )

            data = response.json()
            batch = data.get("conversations", [])
            conversations.extend(batch)

            cursor = data.get("next_cursor")
            if not cursor or not batch:
                break

    return conversations[:limit]


def fetch_conversation_detail(conversation_id: str, api_key: str) -> dict:
    """
    Fetch the full transcript and metadata for a single conversation.

    Args:
        conversation_id: ElevenLabs conversation ID.
        api_key:         ElevenLabs API key.

    Returns:
        Conversation detail dict including transcript messages.
    """
    url = CONVERSATION_URL.format(conversation_id=conversation_id)

    with httpx.Client(timeout=30.0) as client:
        response = client.get(url, headers={"xi-api-key": api_key})

    if response.status_code != 200:
        raise RuntimeError(
            f"Conversation detail API error {response.status_code}: {response.text[:200]}"
        )

    return response.json()


def fetch_with_transcripts(
    agent_id: str,
    api_key: str,
    limit: int = 20,
) -> list[dict]:
    """
    Fetch conversations and enrich each with its full transcript.

    Limits detailed fetching to `limit` most recent conversations to
    avoid excessive API calls in large deployments.

    Args:
        agent_id: ElevenLabs agent ID.
        api_key:  ElevenLabs API key.
        limit:    Number of conversations to enrich with transcripts.

    Returns:
        List of enriched conversation dicts.
    """
    console.print(f"  [dim]Fetching conversation list (limit={limit})…[/dim]")
    conversations = fetch_conversations(agent_id, api_key, limit=limit)

    if not conversations:
        console.print("  [yellow]No conversations found for this agent.[/yellow]")
        return []

    console.print(f"  [dim]Found {len(conversations)} conversations. Fetching transcripts…[/dim]")
    enriched = []

    for i, conv in enumerate(conversations, 1):
        conv_id = conv.get("conversation_id")
        console.print(f"  [dim]Detail[/dim] [{i}/{len(conversations)}] {conv_id}")
        try:
            detail = fetch_conversation_detail(conv_id, api_key)
            enriched.append({**conv, "transcript": detail.get("transcript", [])})
        except RuntimeError as e:
            console.print(f"    [red]✗ Failed:[/red] {e}")
            enriched.append({**conv, "transcript": [], "fetch_error": str(e)})

    return enriched
