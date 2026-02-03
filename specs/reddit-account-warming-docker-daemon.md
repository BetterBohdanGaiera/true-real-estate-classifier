# Plan: Reddit Account Warming Docker Daemon

## Task Description

Build a Docker-based system that automatically warms up Reddit accounts through gradual, human-like engagement. The system will manage multiple Reddit accounts, perform activities (upvoting, commenting, posting, subscribing, following), track warmup progress, and log status in real-time. The warmup follows a 2-week gradual ramp-up from 1-2 actions/day to 20+ actions/day to avoid detection.

## Objective

Create a production-ready, Docker-deployable Reddit account warming daemon that:
- Manages multiple Reddit accounts with secure credential storage in PostgreSQL
- Executes gradual warmup schedules with human-like activity patterns
- Supports both configured subreddit lists and popular subreddit discovery
- Provides real-time status logging and health monitoring
- Survives container restarts with persistent state

## Problem Statement

New Reddit accounts have low karma and limited activity history, making them:
1. Restricted from posting in many subreddits (karma requirements)
2. Flagged by spam filters when they suddenly become active
3. Suspicious to moderators and automated detection systems

A gradual warmup process builds authentic-looking account history, increasing karma and establishing activity patterns that avoid detection.

## Solution Approach

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     REDDIT WARMING DOCKER CONTAINER                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐     Schedule Activity      ┌────────────────────────┐ │
│  │  WarmupDaemon   │ ────────────────────────▶ │    PostgreSQL DB       │ │
│  │  (Main Loop)    │                            │                        │ │
│  └─────────────────┘                            │ - reddit_accounts      │ │
│          │                                      │ - warmup_schedules     │ │
│          │ Execute Actions                      │ - activity_logs        │ │
│          ▼                                      │ - subreddit_targets    │ │
│  ┌─────────────────┐                            └────────────────────────┘ │
│  │  ActivityEngine │                                      ▲               │
│  │                 │                                      │               │
│  │ - Upvote        │     Log Status/Results               │               │
│  │ - Comment       │ ─────────────────────────────────────┘               │
│  │ - Post          │                                                       │
│  │ - Subscribe     │     Reddit API (PRAW)                                │
│  │ - Follow        │ ◀─────────────────────▶ reddit.com                   │
│  └─────────────────┘                                                       │
│                                                                             │
│  ┌─────────────────┐                                                       │
│  │  StatusLogger   │ ──▶ Console (Rich) + Database + Optional Telegram    │
│  │  (Real-time)    │                                                       │
│  └─────────────────┘                                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **PRAW Library**: Official Reddit API wrapper with rate limiting built-in
2. **Database Polling**: Schedule activities via database, survive restarts
3. **Randomized Delays**: Human-like timing with jitter (±30% variance)
4. **Activity Ramp-Up**: Exponential curve from 1-2 → 20+ actions over 14 days
5. **Subreddit Discovery**: Mix of configured targets + popular/trending subreddits
6. **Proxy Support**: Optional proxy rotation per account for IP diversity

## Relevant Files

### Existing Files to Reference

- **`src/sales_agent/daemon.py`**: Reference for daemon pattern, signal handling, Rich console output
- **`src/sales_agent/scheduling/followup_polling_daemon.py`**: Reference for database polling architecture
- **`src/sales_agent/scheduling/scheduled_action_manager.py`**: Reference for PostgreSQL operations with asyncpg
- **`src/sales_agent/crm/models.py`**: Reference for Pydantic model patterns
- **`deployment/docker/docker-compose.yml`**: Reference for Docker configuration

### New Files to Create

```
src/reddit_warmer/
├── __init__.py                    # Package exports
├── daemon.py                      # Main daemon entry point
├── models.py                      # Pydantic models for accounts, activities, config
├── database/
│   ├── __init__.py
│   ├── account_manager.py         # CRUD for reddit_accounts table
│   ├── activity_logger.py         # Log all activities to database
│   └── schedule_manager.py        # Manage warmup schedules
├── engine/
│   ├── __init__.py
│   ├── activity_engine.py         # Execute Reddit actions (upvote, comment, etc.)
│   ├── content_generator.py       # Generate human-like comments
│   └── subreddit_discovery.py     # Find popular/relevant subreddits
├── warmup/
│   ├── __init__.py
│   ├── warmup_scheduler.py        # Calculate daily activity targets
│   └── warmup_strategies.py       # Different warmup curves (gradual, moderate, etc.)
├── config/
│   ├── reddit_accounts.example.json  # Example account config
│   └── subreddit_targets.json     # Target subreddit lists
└── migrations/
    └── 001_reddit_warming_schema.sql  # Database schema

deployment/docker/
├── docker-compose.reddit-warmer.yml  # Standalone docker-compose
└── Dockerfile.reddit-warmer          # Docker image for warmer
```

## Implementation Phases

### Phase 1: Foundation (Database + Models)
- Create PostgreSQL schema for accounts, schedules, activity logs
- Define Pydantic models for all data structures
- Implement account manager with credential encryption
- Set up basic logging infrastructure

### Phase 2: Core Implementation (Engine + Scheduler)
- Implement PRAW-based activity engine (upvote, comment, post, subscribe, follow)
- Create warmup scheduler with gradual ramp-up curve
- Implement subreddit discovery (configured lists + Reddit API popular/trending)
- Add content generator for human-like comments

### Phase 3: Integration & Polish (Daemon + Docker)
- Create main daemon with polling loop
- Implement Rich console status display
- Add Docker configuration (Dockerfile, docker-compose)
- Implement health checks and monitoring
- Add proxy support for IP diversity

## Step by Step Tasks

### 1. Create Database Migration

Create `src/reddit_warmer/migrations/001_reddit_warming_schema.sql`:

```sql
-- Reddit accounts table
CREATE TABLE IF NOT EXISTS reddit_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(255) NOT NULL UNIQUE,
    password_encrypted TEXT NOT NULL,  -- Encrypted with Fernet
    client_id VARCHAR(255) NOT NULL,
    client_secret_encrypted TEXT NOT NULL,
    user_agent VARCHAR(500),

    -- Warmup state
    warmup_started_at TIMESTAMPTZ,
    warmup_day INT DEFAULT 0,  -- Current day in warmup (0-14)
    warmup_status VARCHAR(50) DEFAULT 'pending',  -- pending, active, paused, completed

    -- Account stats (updated after each activity)
    karma_post INT DEFAULT 0,
    karma_comment INT DEFAULT 0,
    account_age_days INT,

    -- Proxy configuration (optional)
    proxy_url TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_activity_at TIMESTAMPTZ
);

-- Activity logs table
CREATE TABLE IF NOT EXISTS reddit_activity_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID REFERENCES reddit_accounts(id) ON DELETE CASCADE,

    activity_type VARCHAR(50) NOT NULL,  -- upvote, downvote, comment, post, subscribe, follow
    subreddit VARCHAR(255),
    target_id VARCHAR(255),  -- Post/comment ID that was acted on
    content TEXT,  -- Comment/post content if applicable

    status VARCHAR(50) DEFAULT 'pending',  -- pending, success, failed, rate_limited
    error_message TEXT,

    executed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Scheduled activities table (for polling daemon)
CREATE TABLE IF NOT EXISTS reddit_scheduled_activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID REFERENCES reddit_accounts(id) ON DELETE CASCADE,

    activity_type VARCHAR(50) NOT NULL,
    subreddit VARCHAR(255),
    scheduled_for TIMESTAMPTZ NOT NULL,

    status VARCHAR(50) DEFAULT 'pending',  -- pending, processing, completed, failed
    started_processing_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Subreddit targets table
CREATE TABLE IF NOT EXISTS reddit_subreddit_targets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subreddit VARCHAR(255) NOT NULL,
    category VARCHAR(100),  -- e.g., "real_estate", "general", "discovered"
    priority INT DEFAULT 5,  -- 1-10, higher = more likely to be selected
    min_karma_required INT DEFAULT 0,
    allow_comments BOOLEAN DEFAULT true,
    allow_posts BOOLEAN DEFAULT false,  -- Most subreddits restrict new account posts

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for efficient polling
CREATE INDEX IF NOT EXISTS idx_reddit_scheduled_pending
    ON reddit_scheduled_activities(scheduled_for, status)
    WHERE status IN ('pending', 'processing');

CREATE INDEX IF NOT EXISTS idx_reddit_activity_logs_account
    ON reddit_activity_logs(account_id, executed_at DESC);

CREATE INDEX IF NOT EXISTS idx_reddit_accounts_warmup_status
    ON reddit_accounts(warmup_status)
    WHERE warmup_status = 'active';
```

### 2. Create Pydantic Models

Create `src/reddit_warmer/models.py`:

```python
"""Pydantic models for Reddit Warmer."""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class WarmupStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class ActivityType(str, Enum):
    UPVOTE = "upvote"
    DOWNVOTE = "downvote"
    COMMENT = "comment"
    POST = "post"
    SUBSCRIBE = "subscribe"
    FOLLOW = "follow"


class ActivityStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"


class RedditAccount(BaseModel):
    """Reddit account for warming."""
    id: Optional[str] = None
    username: str
    password_encrypted: str
    client_id: str
    client_secret_encrypted: str
    user_agent: Optional[str] = None

    warmup_started_at: Optional[datetime] = None
    warmup_day: int = 0
    warmup_status: WarmupStatus = WarmupStatus.PENDING

    karma_post: int = 0
    karma_comment: int = 0
    account_age_days: Optional[int] = None

    proxy_url: Optional[str] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None


class ActivityLog(BaseModel):
    """Log of a Reddit activity."""
    id: Optional[str] = None
    account_id: str
    activity_type: ActivityType
    subreddit: Optional[str] = None
    target_id: Optional[str] = None
    content: Optional[str] = None
    status: ActivityStatus = ActivityStatus.PENDING
    error_message: Optional[str] = None
    executed_at: Optional[datetime] = None


class ScheduledActivity(BaseModel):
    """Activity scheduled for future execution."""
    id: Optional[str] = None
    account_id: str
    activity_type: ActivityType
    subreddit: Optional[str] = None
    scheduled_for: datetime
    status: ActivityStatus = ActivityStatus.PENDING
    started_processing_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class SubredditTarget(BaseModel):
    """Target subreddit for activities."""
    id: Optional[str] = None
    subreddit: str
    category: Optional[str] = None
    priority: int = 5
    min_karma_required: int = 0
    allow_comments: bool = True
    allow_posts: bool = False
    created_at: Optional[datetime] = None


class WarmupConfig(BaseModel):
    """Configuration for warmup behavior."""
    poll_interval_seconds: int = 60  # Check for due activities every minute
    warmup_duration_days: int = 14  # 2 weeks gradual warmup

    # Activity targets per day (day 1 → day 14)
    min_daily_activities_start: int = 1
    max_daily_activities_start: int = 2
    min_daily_activities_end: int = 15
    max_daily_activities_end: int = 25

    # Activity distribution weights
    upvote_weight: float = 0.50  # 50% upvotes
    comment_weight: float = 0.25  # 25% comments
    subscribe_weight: float = 0.15  # 15% subscribes
    follow_weight: float = 0.05  # 5% follows
    post_weight: float = 0.05  # 5% posts (only after karma threshold)

    # Timing
    min_delay_between_actions_seconds: int = 30
    max_delay_between_actions_seconds: int = 300  # 5 minutes
    activity_hours_start: int = 8  # Start activities at 8am
    activity_hours_end: int = 23  # End activities at 11pm

    # Safety
    karma_threshold_for_posting: int = 50
    max_comments_per_subreddit_per_day: int = 2
    cooldown_on_rate_limit_minutes: int = 30


class DaemonStatus(BaseModel):
    """Current daemon status for logging."""
    running: bool = False
    started_at: Optional[datetime] = None
    accounts_active: int = 0
    accounts_total: int = 0
    activities_today: int = 0
    activities_total: int = 0
    last_activity_at: Optional[datetime] = None
    errors_today: int = 0
```

### 3. Implement Account Manager

Create `src/reddit_warmer/database/account_manager.py`:

- CRUD operations for reddit_accounts table
- Encrypt/decrypt passwords using Fernet (cryptography library)
- Get accounts ready for warmup activities
- Update karma stats after activities

### 4. Implement Activity Logger

Create `src/reddit_warmer/database/activity_logger.py`:

- Log all activities to reddit_activity_logs
- Query activity history for rate limiting decisions
- Get activity stats for status display

### 5. Implement Schedule Manager

Create `src/reddit_warmer/database/schedule_manager.py`:

- Create daily activity schedules based on warmup day
- Claim pending activities with `FOR UPDATE SKIP LOCKED`
- Mark activities as completed/failed
- Reset stale processing activities

### 6. Implement Activity Engine

Create `src/reddit_warmer/engine/activity_engine.py`:

```python
"""Execute Reddit activities using PRAW."""
import praw
import random
from typing import Optional
from datetime import datetime, timezone

from ..models import RedditAccount, ActivityType, ActivityLog


class ActivityEngine:
    """Execute Reddit activities for account warming."""

    def __init__(self, account: RedditAccount, decrypt_func):
        self.account = account
        self.reddit = self._create_client(decrypt_func)

    def _create_client(self, decrypt_func) -> praw.Reddit:
        """Create authenticated PRAW client."""
        return praw.Reddit(
            client_id=self.account.client_id,
            client_secret=decrypt_func(self.account.client_secret_encrypted),
            username=self.account.username,
            password=decrypt_func(self.account.password_encrypted),
            user_agent=self.account.user_agent or f"WarmupBot/1.0 by {self.account.username}",
        )

    async def upvote(self, subreddit: str) -> ActivityLog:
        """Upvote a random post in subreddit."""
        try:
            sub = self.reddit.subreddit(subreddit)
            posts = list(sub.hot(limit=25))
            if not posts:
                raise Exception(f"No posts found in r/{subreddit}")

            post = random.choice(posts)
            post.upvote()

            return ActivityLog(
                account_id=self.account.id,
                activity_type=ActivityType.UPVOTE,
                subreddit=subreddit,
                target_id=post.id,
                status="success",
                executed_at=datetime.now(timezone.utc),
            )
        except Exception as e:
            return ActivityLog(
                account_id=self.account.id,
                activity_type=ActivityType.UPVOTE,
                subreddit=subreddit,
                status="failed",
                error_message=str(e),
                executed_at=datetime.now(timezone.utc),
            )

    async def comment(self, subreddit: str, content: str) -> ActivityLog:
        """Comment on a random post in subreddit."""
        # Similar pattern with error handling
        pass

    async def subscribe(self, subreddit: str) -> ActivityLog:
        """Subscribe to a subreddit."""
        try:
            sub = self.reddit.subreddit(subreddit)
            sub.subscribe()
            return ActivityLog(
                account_id=self.account.id,
                activity_type=ActivityType.SUBSCRIBE,
                subreddit=subreddit,
                status="success",
                executed_at=datetime.now(timezone.utc),
            )
        except Exception as e:
            return ActivityLog(
                account_id=self.account.id,
                activity_type=ActivityType.SUBSCRIBE,
                subreddit=subreddit,
                status="failed",
                error_message=str(e),
                executed_at=datetime.now(timezone.utc),
            )

    async def follow_user(self, username: str) -> ActivityLog:
        """Follow a Reddit user."""
        pass

    async def post(self, subreddit: str, title: str, content: str) -> ActivityLog:
        """Create a post in subreddit."""
        pass

    def get_account_karma(self) -> tuple[int, int]:
        """Get current karma stats."""
        me = self.reddit.user.me()
        return me.link_karma, me.comment_karma
```

### 7. Implement Content Generator

Create `src/reddit_warmer/engine/content_generator.py`:

- Generate human-like comments using templates + Claude API
- Match comment style to subreddit tone
- Avoid detection patterns (no repetition, natural language)

### 8. Implement Subreddit Discovery

Create `src/reddit_warmer/engine/subreddit_discovery.py`:

```python
"""Discover subreddits for warming activities."""
import praw
import random
from typing import List


class SubredditDiscovery:
    """Find subreddits for account warming activities."""

    def __init__(self, reddit: praw.Reddit):
        self.reddit = reddit

    def get_popular_subreddits(self, limit: int = 50) -> List[str]:
        """Get popular subreddits from Reddit."""
        return [sub.display_name for sub in self.reddit.subreddits.popular(limit=limit)]

    def get_trending_subreddits(self) -> List[str]:
        """Get currently trending subreddits."""
        # Reddit removed the trending API, use alternative
        return [sub.display_name for sub in self.reddit.subreddits.default(limit=25)]

    def get_related_subreddits(self, subreddit: str) -> List[str]:
        """Get subreddits related to a given one."""
        # Parse sidebar/wiki for related subs
        pass

    def select_subreddit(
        self,
        configured: List[str],
        discovered: List[str],
        account_karma: int,
    ) -> str:
        """Select a subreddit for next activity."""
        # Mix configured (70%) and discovered (30%)
        pool = []
        pool.extend(configured * 7)  # 70% weight
        pool.extend(discovered * 3)  # 30% weight

        return random.choice(pool) if pool else "AskReddit"
```

### 9. Implement Warmup Scheduler

Create `src/reddit_warmer/warmup/warmup_scheduler.py`:

```python
"""Schedule warmup activities based on day and configuration."""
import random
from datetime import datetime, timezone, timedelta
from typing import List

from ..models import WarmupConfig, ActivityType, ScheduledActivity


class WarmupScheduler:
    """Calculate and schedule daily warmup activities."""

    def __init__(self, config: WarmupConfig):
        self.config = config

    def calculate_daily_target(self, warmup_day: int) -> int:
        """Calculate target activities for a given warmup day (0-14)."""
        # Exponential growth curve
        progress = min(warmup_day / self.config.warmup_duration_days, 1.0)

        min_activities = self.config.min_daily_activities_start + \
            (self.config.min_daily_activities_end - self.config.min_daily_activities_start) * progress
        max_activities = self.config.max_daily_activities_start + \
            (self.config.max_daily_activities_end - self.config.max_daily_activities_start) * progress

        return random.randint(int(min_activities), int(max_activities))

    def select_activity_type(self, account_karma: int) -> ActivityType:
        """Select activity type based on weights and karma."""
        weights = {
            ActivityType.UPVOTE: self.config.upvote_weight,
            ActivityType.COMMENT: self.config.comment_weight,
            ActivityType.SUBSCRIBE: self.config.subscribe_weight,
            ActivityType.FOLLOW: self.config.follow_weight,
        }

        # Only allow posting after karma threshold
        if account_karma >= self.config.karma_threshold_for_posting:
            weights[ActivityType.POST] = self.config.post_weight

        # Weighted random selection
        total = sum(weights.values())
        r = random.uniform(0, total)
        cumulative = 0
        for activity_type, weight in weights.items():
            cumulative += weight
            if r <= cumulative:
                return activity_type

        return ActivityType.UPVOTE  # Fallback

    def generate_daily_schedule(
        self,
        account_id: str,
        warmup_day: int,
        account_karma: int,
    ) -> List[ScheduledActivity]:
        """Generate today's activity schedule for an account."""
        target_count = self.calculate_daily_target(warmup_day)

        # Spread activities throughout active hours
        now = datetime.now(timezone.utc)
        today_start = now.replace(
            hour=self.config.activity_hours_start,
            minute=0, second=0, microsecond=0
        )
        today_end = now.replace(
            hour=self.config.activity_hours_end,
            minute=0, second=0, microsecond=0
        )

        # If we're past end time, schedule for tomorrow
        if now >= today_end:
            today_start += timedelta(days=1)
            today_end += timedelta(days=1)

        # If we're before start time, use today's window
        if now < today_start:
            pass  # Already correct
        else:
            today_start = now + timedelta(minutes=5)  # Start in 5 minutes

        # Calculate time slots
        window_seconds = (today_end - today_start).total_seconds()
        avg_gap = window_seconds / target_count if target_count > 0 else 3600

        schedules = []
        current_time = today_start

        for i in range(target_count):
            # Add jitter (±30% of gap)
            jitter = random.uniform(-0.3, 0.3) * avg_gap
            gap = max(
                self.config.min_delay_between_actions_seconds,
                min(avg_gap + jitter, self.config.max_delay_between_actions_seconds * 10)
            )

            scheduled_for = current_time + timedelta(seconds=gap * i)

            if scheduled_for > today_end:
                break

            schedules.append(ScheduledActivity(
                account_id=account_id,
                activity_type=self.select_activity_type(account_karma),
                scheduled_for=scheduled_for,
            ))

        return schedules
```

### 10. Implement Main Daemon

Create `src/reddit_warmer/daemon.py`:

```python
#!/usr/bin/env python3
"""Reddit Account Warming Daemon."""
import asyncio
import signal
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live

from .models import WarmupConfig, DaemonStatus
from .database.account_manager import AccountManager
from .database.schedule_manager import ScheduleManager
from .database.activity_logger import ActivityLogger
from .engine.activity_engine import ActivityEngine
from .engine.subreddit_discovery import SubredditDiscovery
from .warmup.warmup_scheduler import WarmupScheduler

console = Console()


class RedditWarmupDaemon:
    """Main daemon for Reddit account warming."""

    def __init__(self, config: WarmupConfig = None):
        self.config = config or WarmupConfig()
        self.account_manager = AccountManager()
        self.schedule_manager = ScheduleManager()
        self.activity_logger = ActivityLogger()
        self.warmup_scheduler = WarmupScheduler(self.config)

        self.running = False
        self.status = DaemonStatus()

    async def initialize(self) -> None:
        """Initialize all components."""
        console.print("[bold blue]Initializing Reddit Warmup Daemon...[/bold blue]")

        # Initialize database connections
        await self.account_manager.initialize()
        await self.schedule_manager.initialize()
        await self.activity_logger.initialize()

        # Load accounts
        accounts = await self.account_manager.get_active_accounts()
        self.status.accounts_total = len(accounts)
        self.status.accounts_active = len([a for a in accounts if a.warmup_status == "active"])

        console.print(f"  [green]✓[/green] Loaded {self.status.accounts_total} accounts "
                     f"({self.status.accounts_active} active)")

        # Generate daily schedules for active accounts
        for account in accounts:
            if account.warmup_status == "active":
                await self._ensure_daily_schedule(account)

        console.print("[green]Initialization complete[/green]")

    async def _ensure_daily_schedule(self, account) -> None:
        """Ensure account has activities scheduled for today."""
        pending = await self.schedule_manager.get_pending_count(account.id)

        if pending == 0:
            # Generate new schedule
            schedules = self.warmup_scheduler.generate_daily_schedule(
                account_id=account.id,
                warmup_day=account.warmup_day,
                account_karma=account.karma_comment + account.karma_post,
            )

            for schedule in schedules:
                await self.schedule_manager.create(schedule)

            console.print(f"  [cyan]Scheduled {len(schedules)} activities for @{account.username}[/cyan]")

    async def run(self) -> None:
        """Main daemon loop."""
        self.running = True
        self.status.running = True
        self.status.started_at = datetime.now(timezone.utc)

        console.print(Panel.fit(
            "[bold green]Reddit Warmup Daemon Started[/bold green]\n"
            f"Polling interval: {self.config.poll_interval_seconds}s\n"
            "Press Ctrl+C to stop",
            title="Status"
        ))

        try:
            while self.running:
                await self._poll_and_execute()
                await self._update_status_display()
                await asyncio.sleep(self.config.poll_interval_seconds)

        except asyncio.CancelledError:
            console.print("\n[yellow]Shutdown requested...[/yellow]")
        finally:
            await self.shutdown()

    async def _poll_and_execute(self) -> None:
        """Poll for due activities and execute them."""
        # Claim due activities
        activities = await self.schedule_manager.claim_due_activities(limit=5)

        for activity in activities:
            try:
                account = await self.account_manager.get_by_id(activity.account_id)
                if not account:
                    continue

                # Execute activity
                engine = ActivityEngine(account, self.account_manager.decrypt)

                if activity.activity_type == "upvote":
                    result = await engine.upvote(activity.subreddit or "AskReddit")
                elif activity.activity_type == "comment":
                    # Generate comment content
                    result = await engine.comment(activity.subreddit, "Great post!")
                elif activity.activity_type == "subscribe":
                    result = await engine.subscribe(activity.subreddit or "funny")
                else:
                    continue

                # Log result
                await self.activity_logger.log(result)

                # Mark complete
                await self.schedule_manager.mark_completed(activity.id)

                self.status.activities_today += 1
                self.status.activities_total += 1
                self.status.last_activity_at = datetime.now(timezone.utc)

                console.print(f"[green]✓[/green] {activity.activity_type} in r/{activity.subreddit} "
                             f"by @{account.username}")

                # Random delay between activities
                delay = random.randint(
                    self.config.min_delay_between_actions_seconds,
                    self.config.max_delay_between_actions_seconds,
                )
                await asyncio.sleep(delay)

            except Exception as e:
                self.status.errors_today += 1
                console.print(f"[red]✗ Error: {e}[/red]")
                await self.schedule_manager.mark_failed(activity.id, str(e))

    async def _update_status_display(self) -> None:
        """Update the status table display."""
        # Periodic status update (every 5 minutes)
        pass

    def _create_status_table(self) -> Table:
        """Create status table for display."""
        table = Table(title="Reddit Warmup Status")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        if self.status.started_at:
            uptime = datetime.now(timezone.utc) - self.status.started_at
            table.add_row("Uptime", str(uptime).split('.')[0])

        table.add_row("Accounts Active", str(self.status.accounts_active))
        table.add_row("Accounts Total", str(self.status.accounts_total))
        table.add_row("Activities Today", str(self.status.activities_today))
        table.add_row("Activities Total", str(self.status.activities_total))
        table.add_row("Errors Today", str(self.status.errors_today))

        return table

    async def shutdown(self) -> None:
        """Gracefully shutdown."""
        self.running = False
        console.print("[yellow]Shutting down...[/yellow]")

        await self.account_manager.close()
        await self.schedule_manager.close()
        await self.activity_logger.close()

        console.print(Panel.fit(
            f"[bold]Final Stats[/bold]\n"
            f"Activities Executed: {self.status.activities_total}\n"
            f"Errors: {self.status.errors_today}",
            title="Session Summary"
        ))


async def main():
    """Main entry point."""
    daemon = RedditWarmupDaemon()

    loop = asyncio.get_event_loop()

    def signal_handler():
        daemon.running = False

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await daemon.initialize()
        await daemon.run()
    except Exception as e:
        console.print(f"[red bold]Fatal error: {e}[/red bold]")
        raise


if __name__ == "__main__":
    asyncio.run(main())
```

### 11. Create Docker Configuration

Create `deployment/docker/Dockerfile.reddit-warmer`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for package management
RUN pip install uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ ./src/

# Install dependencies
RUN uv sync --frozen

# Environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "from reddit_warmer.models import DaemonStatus; print('OK')" || exit 1

# Run daemon
CMD ["uv", "run", "python", "-m", "reddit_warmer.daemon"]
```

Create `deployment/docker/docker-compose.reddit-warmer.yml`:

```yaml
version: '3.8'

services:
  reddit-warmer:
    build:
      context: ../..
      dockerfile: deployment/docker/Dockerfile.reddit-warmer
    container_name: reddit-warmer
    restart: unless-stopped
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - ENCRYPTION_KEY=${ENCRYPTION_KEY}
      - REDDIT_POLL_INTERVAL_SECONDS=60
      - TZ=UTC
    volumes:
      - ../../src/reddit_warmer/config:/app/config:ro
    depends_on:
      - postgres
    networks:
      - app-network
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  postgres:
    image: postgres:15-alpine
    container_name: reddit-warmer-db
    restart: unless-stopped
    environment:
      - POSTGRES_DB=reddit_warmer
      - POSTGRES_USER=${POSTGRES_USER:-warmer}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ../../src/reddit_warmer/migrations:/docker-entrypoint-initdb.d:ro
    networks:
      - app-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-warmer} -d reddit_warmer"]
      interval: 10s
      timeout: 5s
      retries: 5

networks:
  app-network:
    driver: bridge

volumes:
  postgres-data:
```

### 12. Create Example Configuration

Create `src/reddit_warmer/config/reddit_accounts.example.json`:

```json
{
  "accounts": [
    {
      "username": "your_reddit_username",
      "password": "your_reddit_password",
      "client_id": "your_app_client_id",
      "client_secret": "your_app_client_secret",
      "user_agent": "WarmupBot/1.0 by your_username",
      "proxy_url": null
    }
  ],
  "subreddit_targets": {
    "real_estate": [
      "RealEstate",
      "realestateinvesting",
      "FirstTimeHomeBuyer",
      "homeowners"
    ],
    "general": [
      "AskReddit",
      "todayilearned",
      "mildlyinteresting",
      "pics"
    ]
  }
}
```

### 13. Add Package Dependencies

Add to `pyproject.toml`:

```toml
[project.optional-dependencies]
reddit = [
    "praw>=7.7.0",
    "cryptography>=41.0.0",
]
```

### 14. Validate Implementation

Run validation commands to ensure everything compiles and imports correctly.

## Testing Strategy

### Unit Tests

1. **test_warmup_scheduler.py**
   - Test daily target calculation for each warmup day
   - Test activity type selection with different karma levels
   - Test schedule generation with proper time distribution

2. **test_activity_engine.py**
   - Test PRAW client creation with mocked credentials
   - Test each activity type with mocked Reddit API
   - Test error handling for rate limits and API errors

3. **test_schedule_manager.py**
   - Test claiming activities with row locking
   - Test stale processing recovery
   - Test concurrent access from multiple workers

### Integration Tests

1. **Docker Restart Test**
   - Start warmup, stop container mid-activity
   - Restart container, verify no duplicate activities
   - Verify pending activities resume correctly

2. **Rate Limit Handling**
   - Simulate Reddit API rate limit response
   - Verify cooldown is applied correctly
   - Verify activity resumes after cooldown

### Manual Validation

```bash
# Add test account to database
PYTHONPATH=src uv run python -c "
from reddit_warmer.database.account_manager import AccountManager
import asyncio

async def add_test():
    mgr = AccountManager()
    await mgr.initialize()
    await mgr.add_account(
        username='test_account',
        password='encrypted_password',
        client_id='test_client_id',
        client_secret='encrypted_secret',
    )
    print('Test account added')

asyncio.run(add_test())
"

# Start daemon in test mode
PYTHONPATH=src uv run python -m reddit_warmer.daemon

# Monitor logs
docker-compose -f deployment/docker/docker-compose.reddit-warmer.yml logs -f
```

## Acceptance Criteria

- [ ] Daemon starts successfully and connects to PostgreSQL
- [ ] Accounts can be added with encrypted credentials
- [ ] Daily schedules are generated based on warmup day
- [ ] Activities execute at scheduled times (±30 seconds accuracy)
- [ ] All activity types work: upvote, comment, subscribe, follow, post
- [ ] Activity logs are persisted to database
- [ ] Docker container survives restarts without losing state
- [ ] Status display shows real-time daemon health
- [ ] Rate limit handling works (cooldown on 429 responses)
- [ ] Warmup progression: day 1 = 1-2 activities, day 14 = 20+ activities
- [ ] Subreddit selection uses both configured lists and discovery

## Validation Commands

```bash
# Verify Python syntax of new files
PYTHONPATH=src uv run python -m py_compile src/reddit_warmer/*.py

# Verify imports work
PYTHONPATH=src uv run python -c "from reddit_warmer.daemon import RedditWarmupDaemon; print('OK')"

# Run database migration
psql $DATABASE_URL -f src/reddit_warmer/migrations/001_reddit_warming_schema.sql

# Build Docker image
docker build -f deployment/docker/Dockerfile.reddit-warmer -t reddit-warmer .

# Start with docker-compose
docker-compose -f deployment/docker/docker-compose.reddit-warmer.yml up -d

# Check daemon logs
docker-compose -f deployment/docker/docker-compose.reddit-warmer.yml logs -f reddit-warmer

# Check database for scheduled activities
psql $DATABASE_URL -c "SELECT * FROM reddit_scheduled_activities ORDER BY scheduled_for LIMIT 10;"

# Check activity logs
psql $DATABASE_URL -c "SELECT * FROM reddit_activity_logs ORDER BY executed_at DESC LIMIT 10;"
```

## Notes

### Reddit API Requirements

1. **Create Reddit App**: Go to https://www.reddit.com/prefs/apps and create a "script" type application
2. **Rate Limits**: Reddit allows ~60 requests/minute. PRAW handles this automatically.
3. **Terms of Service**: Automated voting/commenting may violate Reddit TOS. Use at your own risk.

### Security Considerations

1. **Credential Encryption**: Use Fernet symmetric encryption from `cryptography` library
2. **Environment Variables**: Store `ENCRYPTION_KEY` in `.env`, not in code
3. **Proxy Rotation**: Consider using residential proxies for each account to avoid IP bans

### Dependencies to Add

```bash
uv add praw cryptography
```

### Future Enhancements

1. **Telegram Notifications**: Send status updates to Telegram bot
2. **Prometheus Metrics**: Export metrics for Grafana dashboards
3. **Comment AI**: Use Claude to generate contextual comments
4. **Multi-Instance**: Support running multiple daemon instances with distributed locking
