# Plan: Message Events - Edit, Delete, Forward & Reply-to Context

## Task Description
Handle Telegram message events beyond simple new messages: edited messages, deleted messages, forwarded messages, and reply-to context. Currently the system only processes `events.NewMessage` and ignores all other message lifecycle events.

## Objective
Enable the sales agent to:
1. Detect and handle edited messages (update context with new content)
2. Detect deleted messages (clean up or note in context)
3. Recognize forwarded messages (different handling vs original)
4. Capture reply-to context (understand what client is responding to)

## Problem Statement
Current gaps:
- **Edited messages**: Client corrects "100k" to "1M" → agent already responded to wrong amount
- **Deleted messages**: Client deletes sensitive info → still in conversation_history
- **Forwarded messages**: Client forwards competitor offer → agent treats as original message
- **Reply-to context**: Client replies to specific old message → agent doesn't know which one

## Solution Approach
1. Add `events.MessageEdited` handler to daemon
2. Add `events.MessageDeleted` handler (mark in history, don't remove)
3. Extract forward metadata from messages
4. Extract reply_to_msg_id and fetch replied message content
5. Update ConversationMessage model with new metadata fields

## Relevant Files

### Existing Files to Modify
- `src/sales_agent/daemon.py` - Add new event handlers
- `src/sales_agent/crm/models.py` - Update ConversationMessage with new fields
- `src/sales_agent/crm/prospect_manager.py` - Add update/mark methods
- `src/sales_agent/messaging/message_buffer.py` - Handle edit events in buffer
- `src/sales_agent/agent/telegram_agent.py` - Add context about reply-to/forward

### Reference Files
- Telethon documentation for events.MessageEdited, events.MessageDeleted

## Implementation Phases

### Phase 1: Foundation
- Add metadata fields to ConversationMessage (is_edited, is_deleted, is_forwarded, reply_to_id)
- Update serialization/deserialization

### Phase 2: Core Implementation
- Add MessageEdited event handler
- Add MessageDeleted event handler
- Extract forward info from new messages
- Extract and fetch reply-to context

### Phase 3: Integration
- Update agent prompts to understand edited/forwarded context
- Test all event types

## Step by Step Tasks

### 1. Update ConversationMessage Model
- In `src/sales_agent/crm/models.py`, add fields to ConversationMessage:
```python
class ConversationMessage(BaseModel):
    """A single message in conversation history."""
    id: int
    sender: Literal["agent", "prospect"]
    text: str
    timestamp: datetime = Field(default_factory=datetime.now)
    media_type: MessageMediaType = MessageMediaType.TEXT
    # NEW FIELDS
    is_edited: bool = False
    edited_at: Optional[datetime] = None
    original_text: Optional[str] = None  # Text before edit
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    is_forwarded: bool = False
    forward_from: Optional[str] = None  # Original sender name
    reply_to_id: Optional[int] = None  # Message ID this replies to
    reply_to_text: Optional[str] = None  # Cached text of replied message
```

### 2. Add Message Edit Handler to Daemon
- In `src/sales_agent/daemon.py`, after the NewMessage handler registration, add:
```python
@self.client.on(events.MessageEdited(incoming=True))
async def handle_message_edited(event):
    """Handle edited messages from prospects."""
    if not event.is_private:
        return

    sender = await event.get_sender()
    prospect = self.prospect_manager.get_prospect(sender.id)
    if not prospect:
        return

    console.print(f"[yellow]✎ Message edited by {prospect.name}:[/yellow] {event.text[:100]}...")

    # Update conversation history
    self.prospect_manager.mark_message_edited(
        prospect.telegram_id,
        event.id,
        new_text=event.text,
        edited_at=datetime.now()
    )

    # If message is in buffer, update it
    if self.message_buffer.has_pending_buffer(str(sender.id)):
        # Note: Edited message handling in buffer is complex
        # For now, log and let the batch process handle it
        console.print(f"[dim]Note: Edited message while batch pending[/dim]")
```

### 3. Add Message Delete Handler to Daemon
- In `src/sales_agent/daemon.py`, add:
```python
@self.client.on(events.MessageDeleted)
async def handle_message_deleted(event):
    """Handle deleted messages."""
    # Note: MessageDeleted doesn't have sender info easily
    # We need to check if deleted message ID is in any prospect's history
    for msg_id in event.deleted_ids:
        for prospect in self.prospect_manager.get_all_prospects():
            if self.prospect_manager.has_message(prospect.telegram_id, msg_id):
                console.print(f"[red]✗ Message {msg_id} deleted by {prospect.name}[/red]")
                self.prospect_manager.mark_message_deleted(
                    prospect.telegram_id,
                    msg_id
                )
                break
```

### 4. Add Prospect Manager Methods
- In `src/sales_agent/crm/prospect_manager.py`, add:
```python
def has_message(self, telegram_id: int | str, message_id: int) -> bool:
    """Check if a message exists in prospect's history."""
    prospect = self.get_prospect(telegram_id)
    if not prospect:
        return False
    return any(m.id == message_id for m in prospect.conversation_history)

def mark_message_edited(
    self,
    telegram_id: int | str,
    message_id: int,
    new_text: str,
    edited_at: datetime
) -> None:
    """Mark a message as edited and update its text."""
    key = self._normalize_id(telegram_id)
    prospect = self._prospects.get(key)
    if not prospect:
        return

    for msg in prospect.conversation_history:
        if msg.id == message_id:
            msg.original_text = msg.text  # Preserve original
            msg.text = new_text
            msg.is_edited = True
            msg.edited_at = edited_at
            break

    self._save_prospects()

def mark_message_deleted(
    self,
    telegram_id: int | str,
    message_id: int
) -> None:
    """Mark a message as deleted (don't remove, just flag)."""
    key = self._normalize_id(telegram_id)
    prospect = self._prospects.get(key)
    if not prospect:
        return

    for msg in prospect.conversation_history:
        if msg.id == message_id:
            msg.is_deleted = True
            msg.deleted_at = datetime.now()
            break

    self._save_prospects()
```

### 5. Extract Forward Info in Message Handler
- In daemon.py `handle_incoming`, after media detection, add:
```python
# Extract forward info
is_forwarded = event.message.fwd_from is not None
forward_from = None
if is_forwarded and event.message.fwd_from:
    if event.message.fwd_from.from_name:
        forward_from = event.message.fwd_from.from_name
    elif event.message.fwd_from.from_id:
        try:
            fwd_sender = await self.client.get_entity(event.message.fwd_from.from_id)
            forward_from = getattr(fwd_sender, 'first_name', str(event.message.fwd_from.from_id))
        except:
            forward_from = "unknown"

if is_forwarded:
    console.print(f"[cyan]↪ Forwarded message from {forward_from}[/cyan]")
```

### 6. Extract Reply-to Context
- In daemon.py `handle_incoming`, add:
```python
# Extract reply-to context
reply_to_id = None
reply_to_text = None
if event.message.reply_to:
    reply_to_id = event.message.reply_to.reply_to_msg_id
    try:
        replied_msg = await self.client.get_messages(
            event.chat_id,
            ids=reply_to_id
        )
        if replied_msg:
            reply_to_text = replied_msg.text[:200] if replied_msg.text else None
            console.print(f"[dim]↩ Replying to: {reply_to_text[:50]}...[/dim]")
    except Exception as e:
        console.print(f"[dim]Could not fetch replied message: {e}[/dim]")
```

### 7. Update Recording to Include New Fields
- Update `record_response` call to include all new metadata:
```python
self.prospect_manager.record_response(
    prospect.telegram_id,
    event.id,
    message_text,
    media_type=media_result.media_type or "text",
    is_forwarded=is_forwarded,
    forward_from=forward_from,
    reply_to_id=reply_to_id,
    reply_to_text=reply_to_text
)
```

### 8. Update Agent Context Formatting
- In `get_conversation_context`, include metadata:
```python
for msg in messages:
    prefix = ""
    if msg.is_forwarded:
        prefix = f"[Переслано от {msg.forward_from}] "
    if msg.reply_to_text:
        prefix += f"[В ответ на: '{msg.reply_to_text[:30]}...'] "
    if msg.is_edited:
        prefix += "[изменено] "
    if msg.is_deleted:
        prefix += "[удалено] "

    lines.append(f"[{timestamp}] {sender}: {prefix}{msg.text}")
```

### 9. Update Serialization
- In `_save_prospects` and `_load_prospects`, handle all new fields with defaults for backward compatibility

### 10. Validate Implementation
- Test edit detection with real Telegram edit
- Test delete detection
- Test forward recognition
- Test reply-to context capture

## Testing Strategy

### Unit Tests
- Test mark_message_edited() updates correctly
- Test mark_message_deleted() flags correctly
- Test forward extraction from mock event
- Test reply-to extraction from mock event

### Integration Tests
1. Send message, edit it → verify history updated
2. Send message, delete it → verify marked as deleted
3. Forward a message → verify forward_from captured
4. Reply to specific message → verify reply_to_text captured

### Edge Cases
- Edit message multiple times
- Delete message that's in buffer
- Forward from private account (hidden sender)
- Reply to deleted message

## Acceptance Criteria
- [ ] Edited messages update conversation_history with new text and flag
- [ ] Deleted messages marked as deleted (not removed)
- [ ] Forwarded messages capture original sender info
- [ ] Reply-to captures the message being replied to
- [ ] Agent context includes edit/forward/reply metadata
- [ ] No crashes on any event type

## Validation Commands
```bash
# Compile check
uv run python -m py_compile src/sales_agent/daemon.py src/sales_agent/crm/models.py src/sales_agent/crm/prospect_manager.py

# Run daemon and manually test events
PYTHONPATH=src uv run python src/sales_agent/daemon.py
# Then: send message, edit it, delete it, forward something, reply to something
```

## Notes
- MessageDeleted event doesn't contain sender info - need to search history
- Forwarded messages from privacy-enabled accounts may have hidden sender
- Reply-to context fetching adds latency - cache in history
- Edited messages in buffer: complex edge case, may need special handling
- Consider rate limits when fetching reply-to messages
