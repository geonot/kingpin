#!/usr/bin/env python3
"""
Casino Admin CLI Tool

A command-line interface for casino administration tasks including:
- User management (balance updates, user info, etc.)
- Transaction management
- Bonus code management
- Dashboard statistics
- System utilities

Usage:
    python admin_cli.py --help
    python admin_cli.py user update-balance --user-id 123 --amount 1000000
    python admin_cli.py user info --username "player1"
    python admin_cli.py dashboard
"""

import os
import sys
import click
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

# Add the casino_be directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the Flask app directly
from app import app
from models import db, User, Transaction, BonusCode, GameSession
from schemas import UserSchema, AdminUserSchema, TransactionSchema, BonusCodeSchema
from utils.bitcoin import generate_bitcoin_wallet

def format_sats_to_btc(sats: int) -> str:
    """Convert satoshis to BTC format."""
    return f"{sats / 100_000_000:.8f} BTC"

def format_btc_to_sats(btc: str) -> int:
    """Convert BTC string to satoshis."""
    try:
        btc_decimal = Decimal(btc)
        return int(btc_decimal * 100_000_000)
    except:
        raise ValueError(f"Invalid BTC amount: {btc}")

@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def cli(ctx, verbose):
    """Casino Admin CLI - Administrative tools for the casino platform."""
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    
    # Ensure we're in app context
    ctx.obj['app_context'] = app.app_context()
    ctx.obj['app_context'].push()

@cli.group()
def user():
    """User management commands."""
    pass

@cli.group()
def transaction():
    """Transaction management commands."""
    pass

@cli.group()
def bonus():
    """Bonus code management commands."""
    pass

@cli.command()
@click.pass_context
def dashboard(ctx):
    """Display casino dashboard statistics."""
    try:
        total_users = db.session.query(User.id).count()
        total_sessions = db.session.query(GameSession.id).count()
        total_transactions = db.session.query(Transaction.id).count()
        pending_withdrawals = db.session.query(Transaction.id).filter_by(
            status='pending', transaction_type='withdraw'
        ).count()
        total_bonus_codes = db.session.query(BonusCode.id).count()
        active_bonus_codes = db.session.query(BonusCode.id).filter_by(is_active=True).count()
        total_balance_sats = db.session.query(db.func.sum(User.balance)).scalar() or 0
        
        click.echo("\n🎰 Casino Dashboard Statistics")
        click.echo("=" * 40)
        click.echo(f"👥 Total Users: {total_users:,}")
        click.echo(f"🎮 Total Game Sessions: {total_sessions:,}")
        click.echo(f"💳 Total Transactions: {total_transactions:,}")
        click.echo(f"⏳ Pending Withdrawals: {pending_withdrawals:,}")
        click.echo(f"🎁 Total Bonus Codes: {total_bonus_codes:,}")
        click.echo(f"✅ Active Bonus Codes: {active_bonus_codes:,}")
        click.echo(f"💰 Total Platform Balance: {format_sats_to_btc(total_balance_sats)}")
        click.echo("=" * 40)
        
    except Exception as e:
        click.echo(f"❌ Error fetching dashboard data: {e}", err=True)
        sys.exit(1)

@user.command('update-balance')
@click.option('--user-id', type=int, help='User ID')
@click.option('--username', help='Username')
@click.option('--amount', required=True, help='Amount to add/subtract (in satoshis or BTC format like "0.001")')
@click.option('--notes', help='Admin notes for the transaction')
@click.option('--external-tx-id', help='External transaction ID reference')
@click.option('--dry-run', is_flag=True, help='Show what would be done without making changes')
@click.pass_context
def update_balance(ctx, user_id, username, amount, notes, external_tx_id, dry_run):
    """Update a user's balance by ID or username."""
    if not user_id and not username:
        click.echo("❌ Error: Must provide either --user-id or --username", err=True)
        sys.exit(1)
    
    if user_id and username:
        click.echo("❌ Error: Provide either --user-id or --username, not both", err=True)
        sys.exit(1)
    
    try:
        # Parse amount (support both sats and BTC format)
        if '.' in amount:
            amount_sats = format_btc_to_sats(amount)
        else:
            amount_sats = int(amount)
        
        # Find user
        if user_id:
            user = User.query.get(user_id)
            if not user:
                click.echo(f"❌ Error: User with ID {user_id} not found", err=True)
                sys.exit(1)
        else:
            user = User.query.filter_by(username=username).first()
            if not user:
                click.echo(f"❌ Error: User with username '{username}' not found", err=True)
                sys.exit(1)
        
        old_balance = user.balance
        new_balance = old_balance + amount_sats
        
        if dry_run:
            click.echo(f"\n🔍 DRY RUN - No changes will be made:")
            click.echo(f"👤 User: {user.username} (ID: {user.id})")
            click.echo(f"💰 Current Balance: {format_sats_to_btc(old_balance)}")
            click.echo(f"📊 Amount Change: {'+' if amount_sats >= 0 else ''}{format_sats_to_btc(amount_sats)}")
            click.echo(f"💎 New Balance: {format_sats_to_btc(new_balance)}")
            if notes:
                click.echo(f"📝 Notes: {notes}")
            if external_tx_id:
                click.echo(f"🔗 External TX ID: {external_tx_id}")
            return
        
        # Update balance
        user.balance = new_balance
        
        # Create transaction record
        transaction_details = {
            'admin_action': True,
            'old_balance_sats': old_balance,
            'new_balance_sats': new_balance,
            'amount_change_sats': amount_sats
        }
        
        if notes:
            transaction_details['admin_notes'] = notes
        if external_tx_id:
            transaction_details['external_tx_id'] = external_tx_id
        
        transaction_type = 'deposit' if amount_sats >= 0 else 'admin_adjustment'
        transaction = Transaction(
            user_id=user.id,
            amount=abs(amount_sats),
            transaction_type=transaction_type,
            status='completed',
            details=transaction_details
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        click.echo(f"\n✅ Balance updated successfully!")
        click.echo(f"👤 User: {user.username} (ID: {user.id})")
        click.echo(f"💰 Old Balance: {format_sats_to_btc(old_balance)}")
        click.echo(f"💎 New Balance: {format_sats_to_btc(new_balance)}")
        click.echo(f"📊 Change: {'+' if amount_sats >= 0 else ''}{format_sats_to_btc(amount_sats)}")
        click.echo(f"🧾 Transaction ID: {transaction.id}")
        
    except ValueError as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        db.session.rollback()
        click.echo(f"❌ Error updating balance: {e}", err=True)
        sys.exit(1)

@user.command('info')
@click.option('--user-id', type=int, help='User ID')
@click.option('--username', help='Username')
@click.option('--email', help='Email address')
@click.pass_context
def user_info(ctx, user_id, username, email):
    """Get detailed information about a user."""
    if not any([user_id, username, email]):
        click.echo("❌ Error: Must provide either --user-id, --username, or --email", err=True)
        sys.exit(1)
    
    try:
        # Find user
        if user_id:
            user = User.query.get(user_id)
        elif username:
            user = User.query.filter_by(username=username).first()
        else:
            user = User.query.filter_by(email=email).first()
        
        if not user:
            click.echo(f"❌ Error: User not found", err=True)
            sys.exit(1)
        
        # Get recent transactions
        recent_transactions = Transaction.query.filter_by(user_id=user.id)\
                                              .order_by(Transaction.created_at.desc())\
                                              .limit(5).all()
        
        click.echo(f"\n👤 User Information")
        click.echo("=" * 50)
        click.echo(f"🆔 ID: {user.id}")
        click.echo(f"👤 Username: {user.username}")
        click.echo(f"📧 Email: {user.email}")
        click.echo(f"💰 Balance: {format_sats_to_btc(user.balance)}")
        click.echo(f"🏦 Deposit Address: {user.deposit_wallet_address or 'Not set'}")
        click.echo(f"👑 Admin: {'Yes' if user.is_admin else 'No'}")
        click.echo(f"✅ Active: {'Yes' if user.is_active else 'No'}")
        click.echo(f"📅 Created: {user.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        click.echo(f"🕐 Last Login: {user.last_login_at.strftime('%Y-%m-%d %H:%M:%S UTC') if user.last_login_at else 'Never'}")
        
        if recent_transactions:
            click.echo(f"\n📊 Recent Transactions (Last 5)")
            click.echo("-" * 30)
            for tx in recent_transactions:
                status_emoji = "✅" if tx.status == "completed" else "⏳" if tx.status == "pending" else "❌"
                type_emoji = "💰" if tx.transaction_type == "deposit" else "💸" if tx.transaction_type == "withdraw" else "🎮"
                click.echo(f"{status_emoji} {type_emoji} {tx.transaction_type.upper()}: {format_sats_to_btc(tx.amount)} - {tx.created_at.strftime('%Y-%m-%d %H:%M')}")
        
    except Exception as e:
        click.echo(f"❌ Error fetching user info: {e}", err=True)
        sys.exit(1)

@user.command('list')
@click.option('--limit', default=20, help='Number of users to show (default: 20)')
@click.option('--active-only', is_flag=True, help='Show only active users')
@click.option('--admin-only', is_flag=True, help='Show only admin users')
@click.pass_context
def list_users(ctx, limit, active_only, admin_only):
    """List users with optional filters."""
    try:
        query = User.query
        
        if active_only:
            query = query.filter_by(is_active=True)
        if admin_only:
            query = query.filter_by(is_admin=True)
        
        users = query.order_by(User.created_at.desc()).limit(limit).all()
        
        if not users:
            click.echo("No users found matching the criteria.")
            return
        
        click.echo(f"\n👥 Users List (showing {len(users)} users)")
        click.echo("=" * 80)
        click.echo(f"{'ID':<6} {'Username':<20} {'Email':<30} {'Balance (BTC)':<15} {'Status'}")
        click.echo("-" * 80)
        
        for user in users:
            status = []
            if user.is_admin:
                status.append("👑")
            if not user.is_active:
                status.append("❌")
            status_str = "".join(status) if status else "✅"
            
            click.echo(f"{user.id:<6} {user.username:<20} {user.email:<30} {format_sats_to_btc(user.balance):<15} {status_str}")
        
    except Exception as e:
        click.echo(f"❌ Error listing users: {e}", err=True)
        sys.exit(1)

@user.command('create')
@click.option('--username', required=True, help='Username')
@click.option('--email', required=True, help='Email address')
@click.option('--password', help='Password (will be prompted if not provided)')
@click.option('--admin', is_flag=True, help='Create as admin user')
@click.option('--balance', default='0', help='Initial balance in BTC or sats (default: 0)')
@click.pass_context
def create_user(ctx, username, email, password, admin, balance):
    """Create a new user."""
    try:
        # Check if user already exists
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            if existing_user.username == username:
                click.echo(f"❌ Error: Username '{username}' already exists", err=True)
            else:
                click.echo(f"❌ Error: Email '{email}' already exists", err=True)
            sys.exit(1)
        
        # Get password if not provided
        if not password:
            password = click.prompt("Enter password", hide_input=True, confirmation_prompt=True)
        
        # Parse balance
        if '.' in balance:
            balance_sats = format_btc_to_sats(balance)
        else:
            balance_sats = int(balance)
        
        # Generate wallet address
        wallet_address = generate_bitcoin_wallet()
        if not wallet_address:
            click.echo("❌ Error: Failed to generate wallet address", err=True)
            sys.exit(1)
        
        # Create user
        user = User(
            username=username,
            email=email,
            password=User.hash_password(password),
            is_admin=admin,
            balance=balance_sats,
            deposit_wallet_address=wallet_address
        )
        
        db.session.add(user)
        db.session.commit()
        
        click.echo(f"\n✅ User created successfully!")
        click.echo(f"👤 Username: {user.username}")
        click.echo(f"📧 Email: {user.email}")
        click.echo(f"🆔 ID: {user.id}")
        click.echo(f"👑 Admin: {'Yes' if user.is_admin else 'No'}")
        click.echo(f"💰 Balance: {format_sats_to_btc(user.balance)}")
        click.echo(f"🏦 Deposit Address: {user.deposit_wallet_address}")
        
    except ValueError as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        db.session.rollback()
        click.echo(f"❌ Error creating user: {e}", err=True)
        sys.exit(1)

@transaction.command('list')
@click.option('--user-id', type=int, help='Filter by user ID')
@click.option('--username', help='Filter by username')
@click.option('--type', 'tx_type', help='Filter by transaction type (deposit, withdraw, etc.)')
@click.option('--status', help='Filter by status (pending, completed, rejected)')
@click.option('--limit', default=20, help='Number of transactions to show (default: 20)')
@click.pass_context
def list_transactions(ctx, user_id, username, tx_type, status, limit):
    """List transactions with optional filters."""
    try:
        query = Transaction.query
        
        # Apply filters
        if user_id:
            query = query.filter_by(user_id=user_id)
        elif username:
            user = User.query.filter_by(username=username).first()
            if not user:
                click.echo(f"❌ Error: User '{username}' not found", err=True)
                sys.exit(1)
            query = query.filter_by(user_id=user.id)
        
        if tx_type:
            query = query.filter_by(transaction_type=tx_type)
        if status:
            query = query.filter_by(status=status)
        
        transactions = query.order_by(Transaction.created_at.desc()).limit(limit).all()
        
        if not transactions:
            click.echo("No transactions found matching the criteria.")
            return
        
        click.echo(f"\n💳 Transactions List (showing {len(transactions)} transactions)")
        click.echo("=" * 120)
        click.echo(f"{'ID':<6} {'User':<15} {'Type':<12} {'Amount (BTC)':<15} {'Status':<10} {'Date':<20}")
        click.echo("-" * 120)
        
        for tx in transactions:
            user = User.query.get(tx.user_id)
            username_display = user.username if user else f"ID:{tx.user_id}"
            
            status_emoji = "✅" if tx.status == "completed" else "⏳" if tx.status == "pending" else "❌"
            
            click.echo(f"{tx.id:<6} {username_display:<15} {tx.transaction_type:<12} {format_sats_to_btc(tx.amount):<15} {status_emoji}{tx.status:<9} {tx.created_at.strftime('%Y-%m-%d %H:%M')}")
        
    except Exception as e:
        click.echo(f"❌ Error listing transactions: {e}", err=True)
        sys.exit(1)

@transaction.command('approve')
@click.argument('transaction_id', type=int)
@click.option('--notes', help='Admin notes for approval')
@click.pass_context
def approve_transaction(ctx, transaction_id, notes):
    """Approve a pending withdrawal transaction."""
    try:
        tx = Transaction.query.get(transaction_id)
        if not tx:
            click.echo(f"❌ Error: Transaction {transaction_id} not found", err=True)
            sys.exit(1)
        
        if tx.transaction_type != 'withdraw':
            click.echo(f"❌ Error: Can only approve withdrawal transactions", err=True)
            sys.exit(1)
        
        if tx.status != 'pending':
            click.echo(f"❌ Error: Transaction is not pending (current status: {tx.status})", err=True)
            sys.exit(1)
        
        # Update transaction
        tx.status = 'completed'
        details = tx.details or {}
        if notes:
            details['admin_notes'] = notes
        details['approved_at'] = datetime.now(timezone.utc).isoformat()
        tx.details = details
        
        db.session.commit()
        
        click.echo(f"✅ Transaction {transaction_id} approved successfully!")
        click.echo(f"💸 Amount: {format_sats_to_btc(tx.amount)}")
        if notes:
            click.echo(f"📝 Notes: {notes}")
        
    except Exception as e:
        db.session.rollback()
        click.echo(f"❌ Error approving transaction: {e}", err=True)
        sys.exit(1)

@transaction.command('reject')
@click.argument('transaction_id', type=int)
@click.option('--notes', help='Admin notes for rejection')
@click.pass_context
def reject_transaction(ctx, transaction_id, notes):
    """Reject a pending withdrawal transaction and refund the user."""
    try:
        tx = Transaction.query.get(transaction_id)
        if not tx:
            click.echo(f"❌ Error: Transaction {transaction_id} not found", err=True)
            sys.exit(1)
        
        if tx.transaction_type != 'withdraw':
            click.echo(f"❌ Error: Can only reject withdrawal transactions", err=True)
            sys.exit(1)
        
        if tx.status != 'pending':
            click.echo(f"❌ Error: Transaction is not pending (current status: {tx.status})", err=True)
            sys.exit(1)
        
        # Refund user
        user = User.query.get(tx.user_id)
        if not user:
            click.echo(f"❌ Error: User not found for refund", err=True)
            sys.exit(1)
        
        user.balance += tx.amount
        
        # Update transaction
        tx.status = 'rejected'
        details = tx.details or {}
        if notes:
            details['admin_notes'] = notes
        details['rejected_at'] = datetime.now(timezone.utc).isoformat()
        details['refunded_amount_sats'] = tx.amount
        tx.details = details
        
        db.session.commit()
        
        click.echo(f"❌ Transaction {transaction_id} rejected and refunded!")
        click.echo(f"💸 Refunded Amount: {format_sats_to_btc(tx.amount)}")
        click.echo(f"👤 User: {user.username}")
        if notes:
            click.echo(f"📝 Notes: {notes}")
        
    except Exception as e:
        db.session.rollback()
        click.echo(f"❌ Error rejecting transaction: {e}", err=True)
        sys.exit(1)

@bonus.command('list')
@click.option('--active-only', is_flag=True, help='Show only active bonus codes')
@click.option('--limit', default=20, help='Number of bonus codes to show (default: 20)')
@click.pass_context
def list_bonus_codes(ctx, active_only, limit):
    """List bonus codes."""
    try:
        query = BonusCode.query
        
        if active_only:
            query = query.filter_by(is_active=True)
        
        bonus_codes = query.order_by(BonusCode.created_at.desc()).limit(limit).all()
        
        if not bonus_codes:
            click.echo("No bonus codes found.")
            return
        
        click.echo(f"\n🎁 Bonus Codes List (showing {len(bonus_codes)} codes)")
        click.echo("=" * 100)
        click.echo(f"{'ID':<6} {'Code':<15} {'Type':<12} {'Value (BTC)':<15} {'Uses':<10} {'Active':<8} {'Created'}")
        click.echo("-" * 100)
        
        for code in bonus_codes:
            uses_display = f"{code.uses_remaining or '∞'}"
            active_display = "✅" if code.is_active else "❌"
            value_btc = format_sats_to_btc(code.bonus_value_sats) if code.bonus_value_sats else "N/A"
            
            click.echo(f"{code.id:<6} {code.code_id:<15} {code.bonus_type:<12} {value_btc:<15} {uses_display:<10} {active_display:<8} {code.created_at.strftime('%Y-%m-%d')}")
        
    except Exception as e:
        click.echo(f"❌ Error listing bonus codes: {e}", err=True)
        sys.exit(1)

@bonus.command('create')
@click.option('--code', required=True, help='Bonus code string')
@click.option('--type', 'bonus_type', required=True, type=click.Choice(['fixed', 'percentage']), help='Bonus type')
@click.option('--value', required=True, help='Bonus value (BTC for fixed, percentage for percentage type)')
@click.option('--description', help='Bonus code description')
@click.option('--uses', type=int, help='Number of uses allowed (unlimited if not specified)')
@click.option('--min-deposit', help='Minimum deposit required in BTC')
@click.option('--wagering-multiplier', type=float, default=1.0, help='Wagering requirement multiplier (default: 1.0)')
@click.pass_context
def create_bonus_code(ctx, code, bonus_type, value, description, uses, min_deposit, wagering_multiplier):
    """Create a new bonus code."""
    try:
        # Check if code already exists
        existing_code = BonusCode.query.filter_by(code_id=code).first()
        if existing_code:
            click.echo(f"❌ Error: Bonus code '{code}' already exists", err=True)
            sys.exit(1)
        
        # Parse values
        if bonus_type == 'fixed':
            bonus_value_sats = format_btc_to_sats(value)
            bonus_percentage = None
        else:
            bonus_value_sats = None
            bonus_percentage = float(value)
            if bonus_percentage <= 0 or bonus_percentage > 100:
                raise ValueError("Percentage must be between 0 and 100")
        
        min_deposit_sats = None
        if min_deposit:
            min_deposit_sats = format_btc_to_sats(min_deposit)
        
        # Create bonus code
        bonus_code = BonusCode(
            code_id=code,
            bonus_type=bonus_type,
            bonus_value_sats=bonus_value_sats,
            bonus_percentage=bonus_percentage,
            description=description,
            uses_remaining=uses,
            min_deposit_sats=min_deposit_sats,
            wagering_multiplier=wagering_multiplier,
            is_active=True
        )
        
        db.session.add(bonus_code)
        db.session.commit()
        
        click.echo(f"\n✅ Bonus code created successfully!")
        click.echo(f"🎁 Code: {bonus_code.code_id}")
        click.echo(f"📝 Type: {bonus_code.bonus_type}")
        if bonus_type == 'fixed':
            click.echo(f"💰 Value: {format_sats_to_btc(bonus_code.bonus_value_sats)}")
        else:
            click.echo(f"📊 Percentage: {bonus_code.bonus_percentage}%")
        click.echo(f"🔢 Uses: {bonus_code.uses_remaining or 'Unlimited'}")
        if min_deposit_sats:
            click.echo(f"💳 Min Deposit: {format_sats_to_btc(min_deposit_sats)}")
        click.echo(f"🎯 Wagering Multiplier: {wagering_multiplier}x")
        
    except ValueError as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        db.session.rollback()
        click.echo(f"❌ Error creating bonus code: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.option('--backup-file', help='Backup file path (default: casino_backup_YYYYMMDD_HHMMSS.sql)')
@click.pass_context
def backup(ctx, backup_file):
    """Create a database backup."""
    if not backup_file:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f"casino_backup_{timestamp}.sql"
    
    try:
        import subprocess
        
        # Get database URL from config
        db_url = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        
        if db_url.startswith('sqlite:///'):
            # SQLite backup
            db_path = db_url.replace('sqlite:///', '')
            subprocess.run(['cp', db_path, backup_file], check=True)
            click.echo(f"✅ SQLite database backed up to: {backup_file}")
        else:
            click.echo("❌ Database backup only supported for SQLite currently", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"❌ Error creating backup: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.pass_context
def cleanup(ctx):
    """Cleanup old sessions and temporary data."""
    try:
        from datetime import timedelta
        
        # Clean up old game sessions (older than 7 days)
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
        old_sessions = GameSession.query.filter(GameSession.created_at < cutoff_date).count()
        
        if old_sessions > 0:
            GameSession.query.filter(GameSession.created_at < cutoff_date).delete()
            click.echo(f"🧹 Cleaned up {old_sessions} old game sessions")
        
        db.session.commit()
        click.echo("✅ Cleanup completed")
        
    except Exception as e:
        db.session.rollback()
        click.echo(f"❌ Error during cleanup: {e}", err=True)
        sys.exit(1)

if __name__ == '__main__':
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\n\n👋 Admin CLI interrupted by user")
        sys.exit(0)
    except Exception as e:
        click.echo(f"\n❌ Unexpected error: {e}", err=True)
        sys.exit(1)
    finally:
        # Clean up app context
        try:
            if hasattr(click.get_current_context().obj, 'app_context'):
                click.get_current_context().obj['app_context'].pop()
        except:
            pass