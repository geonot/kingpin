# Sportsbook Platform: Design and Development Document (Integrated with Kingpin Casino)

## 1. Introduction

This document outlines the design and development plan for a new sportsbook module to be integrated within the existing Kingpin Casino platform. The sportsbook will leverage Kingpin's existing user accounts, authentication, and balance management systems (Bitcoin-based, denominated in satoshis).

## 2. Goals

*   Develop a functional online sportsbook module seamlessly integrated with Kingpin Casino.
*   Utilize existing Kingpin user accounts, authentication (Flask-JWT-Extended with HTTP-only cookies and CSRF protection), and user balances (BigInteger satoshis).
*   Support major North American sports leagues (NFL, NBA, MLB, NHL) initially, with a plan for expansion.
*   Implement core betting functionalities: event listing, odds display, bet placement, and bet history.
*   Ensure all financial transactions (bet placement, winnings) are recorded in Kingpin's existing `Transaction` table.

## 3. Scope

### 3.1. Included Sports and Leagues (Initial Focus)

*   **Basketball:** NBA
*   **American Football:** NFL
*   **Baseball:** MLB
*   **Ice Hockey:** NHL

### 3.2. Suggested Additional Sports/Leagues (for future expansion)

*   **Soccer:** MLS, Premier League, La Liga, Serie A, Bundesliga, UEFA Champions League, etc.
*   **Tennis:** ATP, WTA (Grand Slams, Masters)
*   **Golf:** PGA Tour, European Tour (Majors)
*   **MMA:** UFC, Bellator
*   **Boxing:** Major title fights
*   **Motorsports:** Formula 1, NASCAR
*   **eSports:** League of Legends (LoL), Counter-Strike: Global Offensive (CS:GO), Dota 2

### 3.3. Core Features (Leveraging Kingpin Infrastructure)

*   **User Management (Leveraged from Kingpin):**
    *   Uses existing Kingpin user registration, login, logout.
    *   Sportsbook access is granted to any authenticated Kingpin user.
*   **Sports & Events Display:**
    *   Listing available sports.
    *   Listing leagues within sports.
    *   Listing upcoming/recent events (games/matches) for selected leagues (date, time, participants).
    *   Displaying scores/results for past events.
*   **Odds Display:**
    *   Show odds for various bet types for upcoming events.
    *   Initial bet types:
        *   Moneyline (Winner of the event)
        *   Point Spread
        *   Totals (Over/Under)
*   **Betting (Integrated with Kingpin Balance):**
    *   Bet Slip functionality within the Kingpin FE.
    *   Enter stake amount (in satoshis).
    *   Bet placement debits `User.balance` directly.
    *   A `Transaction` record is created with a new `transaction_type` (e.g., `sportsbook_bet_placed`).
*   **Account Management (Integrated with Kingpin):**
    *   User balance is the existing `User.balance` (satoshis).
    *   Sportsbook bet history (pending, won, lost, refunded).
    *   Sportsbook transactions visible in Kingpin's transaction history, filtered by new types.
*   **Administration (Simplified - for initial data population & settlement):**
    *   Endpoints within the `casino_be` admin scope to:
        *   Add/update sports, leagues, teams.
        *   Add/update events and their odds.
        *   Settle events (input final scores), which triggers bet settlement logic.
        *   Bet settlement credits/refunds `User.balance` and creates appropriate `Transaction` records (e.g., `sportsbook_bet_won`, `sportsbook_bet_refund`).

### 3.4. Out of Scope (for Initial Version)

*   Modifications to Kingpin's existing crypto deposit/withdrawal process (sportsbook uses existing balance).
*   Advanced bet types (parlays, teasers, props, futures, live betting) - can be future enhancements.
*   Complex risk management systems specific to sportsbook.
*   Automated odds generation from external feeds (manual input or placeholders initially).
*   Live score/odds updates (page refresh or manual admin updates initially).

## 4. System Architecture (Integration into Kingpin)

The sportsbook will be a new module within the existing Kingpin Casino client-server architecture.

*   **Frontend (`casino_fe` - Vue.js):**
    *   New Vue components and views for sportsbook functionalities, integrated into the existing Kingpin layout and navigation.
    *   Utilizes existing `api.js` service (or an extension of it) for backend communication, handling JWT cookies and CSRF tokens automatically.
*   **Backend (`casino_be` - Python/Flask):**
    *   New Flask Blueprints for sportsbook APIs (e.g., `/api/sportsbook/...`).
    *   New SQLAlchemy models for sportsbook entities.
    *   Services for managing sports data, odds, bet placement, and settlement.
    *   Direct interaction with existing `User` and `Transaction` models for balance updates and financial logging.
    *   Authentication handled by existing Flask-JWT-Extended setup.
*   **Database (Existing Kingpin DB - likely SQLite for dev, PostgreSQL/MySQL for prod):**
    *   New tables for sportsbook entities will be added to the Kingpin database via Alembic migrations.

### 4.1. Technology Stack (Inherited from Kingpin)

*   **Backend:** Python (Flask), SQLAlchemy, Flask-JWT-Extended.
*   **Database:** Existing Kingpin database (e.g., PostgreSQL, uses Alembic for migrations). Balances stored as BigInteger (satoshis).
*   **Frontend:** Vue.js (likely Vue 2 or 3 with Vuex and Vue Router).
*   **API:** RESTful, extending the existing Kingpin API.

## 5. Data Model (New and Modified Entities)

### 5.1. Existing Kingpin Models to be Leveraged/Modified:

*   **`User` (casino_be.models.User):**
    *   No direct schema changes needed. `balance` (BigInteger) will be used for stakes/winnings.
    *   A new relationship `sports_bets = db.relationship('SportsBet', back_populates='user', lazy='dynamic')` will be added.
*   **`Transaction` (casino_be.models.Transaction):**
    *   A new nullable foreign key `sports_bet_id = db.Column(db.Integer, db.ForeignKey('sports_bet.id', ondelete='SET NULL'), nullable=True, index=True)` will be added.
    *   A new relationship `sports_bet = db.relationship('SportsBet', backref=db.backref('transactions', lazy='dynamic'))` will be added.
    *   New `transaction_type` enum values: `'sportsbook_bet_placed'`, `'sportsbook_bet_won'`, `'sportsbook_bet_lost'`, `'sportsbook_bet_refund'`.

### 5.2. New Sportsbook Models:

*   **`Sport`:**
    *   `id` (PK, Integer)
    *   `name` (String, unique, e.g., "Basketball", "Soccer")
    *   `slug` (String, unique, e.g., "basketball", "soccer")
    *   `is_active` (Boolean, default True)
*   **`League`:**
    *   `id` (PK, Integer)
    *   `sport_id` (FK to `Sport.id`)
    *   `name` (String, unique within sport, e.g., "NBA", "Premier League")
    *   `slug` (String, unique, e.g., "nba", "premier-league")
    *   `is_active` (Boolean, default True)
    *   `sport` (Relationship to `Sport`)
*   **`Team`:**
    *   `id` (PK, Integer)
    *   `league_id` (FK to `League.id`)
    *   `name` (String, unique within league, e.g., "Los Angeles Lakers")
    *   `short_name` (String, e.g., "LAL")
    *   `slug` (String, unique)
    *   `logo_url` (String, nullable)
    *   `is_active` (Boolean, default True)
    *   `league` (Relationship to `League`)
*   **`Event` (Game/Match):**
    *   `id` (PK, Integer)
    *   `league_id` (FK to `League.id`)
    *   `home_team_id` (FK to `Team.id`)
    *   `away_team_id` (FK to `Team.id`)
    *   `event_datetime` (DateTime(timezone=True), UTC)
    *   `status` (String, e.g., "Scheduled", "InProgress", "Finished", "Postponed", "Cancelled")
    *   `home_score` (Integer, Nullable)
    *   `away_score` (Integer, Nullable)
    *   `winner_team_id` (FK to `Team.id`, Nullable)
    *   `details_json` (JSON, Nullable, for extra info like period scores, specific game stats)
    *   `created_at`, `updated_at` (DateTime(timezone=True))
    *   `league`, `home_team`, `away_team`, `winning_team` (Relationships)
*   **`Market` (Bet Type for an Event):**
    *   `id` (PK, Integer)
    *   `event_id` (FK to `Event.id`)
    *   `market_type` (String, e.g., "moneyline_2way", "spread_2way", "total_2way_points")
    *   `line_details_json` (JSON, Nullable, e.g., for spread `{"hdp": -7.5, "home_price": -110, "away_price": -110}` or for total `{"points": 210.5, "over_price": -110, "under_price": -110}`)
    *   `is_active` (Boolean, default True)
    *   `settlement_rules_json` (JSON, Nullable, for complex settlement if needed)
    *   `event` (Relationship to `Event`)
*   **`Odds`:** (Represents a specific pickable outcome within a Market)
    *   `id` (PK, Integer)
    *   `market_id` (FK to `Market.id`)
    *   `selection_identifier` (String, e.g., "home", "away", "over", "under", or team_id for specific props)
    *   `display_name` (String, e.g., "Los Angeles Lakers", "Over 210.5")
    *   `decimal_value` (Numeric(10,4), e.g., 1.91, 2.50. Store as decimal for precision)
    *   `american_value` (Integer, e.g., -110, +150. Can be derived or stored)
    *   `is_active` (Boolean, default True)
    *   `last_updated` (DateTime(timezone=True))
    *   `market` (Relationship to `Market`)
*   **`SportsBet`:**
    *   `id` (PK, Integer)
    *   `user_id` (FK to `User.id`)
    *   `odds_id` (FK to `Odds.id` - the specific odds line taken by the user)
    *   `stake_satoshis` (BigInteger, amount wagered)
    *   `potential_payout_satoshis` (BigInteger, calculated at time of bet)
    *   `actual_winnings_satoshis` (BigInteger, Nullable, populated on settlement)
    *   `status` (String, e.g., "Pending", "Won", "Lost", "Void/Refunded", "CashedOut")
    *   `placed_at` (DateTime(timezone=True))
    *   `settled_at` (DateTime(timezone=True), Nullable)
    *   `bet_slip_details_json` (JSON, e.g., selections if it was part of a multi-bet slip later)
    *   `user`, `odds_line` (Relationships)

## 6. API Design (Extending Kingpin API - RESTful)

All new endpoints will be under a new Blueprint, e.g., `/api/sportsbook`. Authentication via existing JWT cookies and CSRF protection applies.

### 6.1. Authentication (Leveraged from Kingpin)

*   No changes. Frontend uses existing `/api/login`, `/api/register`, `/api/logout`, `/api/refresh`, `/api/me`, `/api/csrf-token`.

### 6.2. User-Facing Sportsbook Endpoints

*   **Sports & Events Data:**
    *   `GET /api/sportsbook/sports` -> List of active sports.
    *   `GET /api/sportsbook/sports/{sport_slug}/leagues` -> List of active leagues for a sport.
    *   `GET /api/sportsbook/leagues/{league_slug}/events` -> List of events for a league.
        *   Query params: `?status=scheduled|finished`, `?date_from=YYYY-MM-DD`, `?limit=N`, `?offset=N`.
    *   `GET /api/sportsbook/events/{event_id}` -> Detailed event info, including available markets and their odds.
*   **Betting:**
    *   `POST /api/sportsbook/bets` - (Authenticated, CSRF Protected)
        *   Payload: `{ "odds_id": <int>, "stake_satoshis": <int> }`
        *   Response: Bet details or error.
        *   Logic: Validates user, odds, balance. Debits `User.balance`. Creates `SportsBet` and `Transaction` records.
    *   `GET /api/sportsbook/bets/me` - (Authenticated)
        *   Response: Paginated list of current user's sports bets.
        *   Query params: `?status=pending|won|lost`, `?limit=N`, `?offset=N`.
*   **User Balance & Transactions (Leveraged from Kingpin):**
    *   `GET /api/balance` - (Existing Kingpin endpoint)
    *   `GET /api/transactions` - (Existing Kingpin endpoint, will show new sportsbook transaction types)

### 6.3. Admin Endpoints (Under existing admin protection if available, or new)

*   `POST /api/admin/sportsbook/sports` - { name, slug }
*   `PUT /api/admin/sportsbook/sports/{sport_id}` - { name, slug, is_active }
*   `POST /api/admin/sportsbook/leagues` - { sport_id, name, slug }
*   `PUT /api/admin/sportsbook/leagues/{league_id}` - { ... }
*   `POST /api/admin/sportsbook/teams` - { league_id, name, short_name, slug, logo_url }
*   `PUT /api/admin/sportsbook/teams/{team_id}` - { ... }
*   `POST /api/admin/sportsbook/events` - { league_id, home_team_id, away_team_id, event_datetime, status }
*   `PUT /api/admin/sportsbook/events/{event_id}` - { ... scores, status ... }
*   `POST /api/admin/sportsbook/events/{event_id}/markets` - { market_type, line_details_json }
*   `PUT /api/admin/sportsbook/markets/{market_id}` - { ... }
*   `POST /api/admin/sportsbook/markets/{market_id}/odds` - { selection_identifier, display_name, decimal_value, american_value }
*   `PUT /api/admin/sportsbook/odds/{odds_id}` - { ... }
*   `POST /api/admin/sportsbook/events/{event_id}/settle`
    *   Payload: `{ "home_score": <int>, "away_score": <int> }`
    *   Logic: Updates event score and status to 'Finished'. Derives the winner based on scores. Triggers settlement of all `SportsBet` records associated with the event (updates `User.balance` and creates `Transaction` records for wins/refunds).

## 7. Frontend Design (Vue.js components within Kingpin `casino_fe`)

*   **Layout:** Sportsbook section will be accessible via Kingpin's main navigation. UI should be consistent with Kingpin's existing theme.
*   **Core Views/Components:**
    *   **SportsNavigation:** Component to list sports and leagues.
    *   **EventList:** Displays events for a selected league (teams, time, primary odds).
    *   **EventDetail:** Full event details with all markets and odds. Clicking odds adds to BetSlip.
    *   **BetSlip:**
        *   Integrated into the Kingpin UI (e.g., sidebar).
        *   Shows selections, allows stake input (satoshis), calculates potential payout.
        *   "Place Bet" button triggers `POST /api/sportsbook/bets`.
    *   **MySportsBets:** View to display user's bet history (pending, settled).
*   **State Management (Vuex):**
    *   Leverage existing user auth state.
    *   May need new Vuex modules for sportsbook data (sports, events, odds).
    *   User balance is already in Vuex store, will update automatically via existing mechanisms when bets are placed/won.

## 8. Development Plan (Phased Approach - Aligned with Current Plan)

1.  **Investigate Kingpin Casino and Revise Design (This document - Complete)**
2.  **Seek User Approval for Revised Design Document.**
3.  **Backend Implementation (Phase 1 - Core Sportsbook Logic & Kingpin Integration):**
    *   Add new sportsbook models (`Sport`, `League`, `Team`, `Event`, `Market`, `Odds`, `SportsBet`) to `casino_be/models.py`.
    *   Add FK `sports_bet_id` to `Transaction` model.
    *   Create Alembic migrations for new models and `Transaction` modification.
    *   Develop basic admin APIs for CRUD operations on sports, leagues, teams, events, markets, odds.
    *   Develop user-facing APIs for listing sports, leagues, events, and event details (read-only).
4.  **Frontend Implementation (Phase 1 - Basic Structure and Event Display):**
    *   Create basic Vue components in `casino_fe` for SportsNavigation, EventList, EventDetail.
    *   Integrate these into Kingpin's navigation/routing.
    *   Fetch and display data from the new backend APIs.
5.  **Backend Implementation (Phase 2 - Betting Placement & Settlement Logic):**
    *   Implement `POST /api/sportsbook/bets` API:
        *   Validate user session (via `@jwt_required()`).
        *   Validate stake against `current_user.balance`.
        *   Debit `current_user.balance`.
        *   Create `SportsBet` record.
        *   Create `Transaction` record (type `sportsbook_bet_placed`).
    *   Implement `POST /api/admin/sportsbook/events/{event_id}/settle` API:
        *   Update event scores/status.
        *   Iterate through related `SportsBet` records.
        *   For winning bets: credit `User.balance`, create `Transaction` (type `sportsbook_bet_won`).
        *   For refunded bets: credit `User.balance`, create `Transaction` (type `sportsbook_bet_refund`).
        *   Update `SportsBet` statuses.
6.  **Frontend Implementation (Phase 2 - Placing Bets & Bet History):**
    *   Implement BetSlip component functionality (add selection, input stake, place bet).
    *   Call `POST /api/sportsbook/bets` ensuring CSRF token is sent.
    *   Implement `MySportsBets` view to call `GET /api/sportsbook/bets/me`.
7.  **Testing, Refinement, Documentation, Submission (as per original plan steps).**

## 9. Key Integration Points & Considerations

*   **Balance Denomination:** All monetary values (stakes, payouts, balances) are BigInteger satoshis.
*   **Authentication & CSRF:** Handled by existing Kingpin mechanisms.
*   **Transaction Log:** All sportsbook financial operations must be recorded in Kingpin's `Transaction` table.
*   **Database Migrations:** Use Alembic to manage schema changes.
*   **Bonus System Interaction:**
    *   Need to clarify if sportsbook stakes contribute to `UserBonus.wagering_progress_sats`.
    *   If so, the bet placement and settlement logic must update this progress.
    *   Withdrawal checks in Kingpin for active bonuses will apply to balances that include sportsbook winnings.
*   **Error Handling:** Follow existing Kingpin error handling patterns and custom exceptions.

## 10. Future Enhancements

*   (As per original document, e.g., live betting, parlays, automated odds feeds)

## 11. Non-Functional Requirements

*   (As per original document, e.g., security, scalability, usability)
```
