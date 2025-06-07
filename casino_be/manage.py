#!/bin/bash
echo "Dummy manage.py called with: $@" # For debugging
shopt -s extglob # Enable extglob for an alternative pattern matching
case "$1" in
    db)
        case "$2" in
            @(init|migrate|upgrade))
                echo "Dummy manage.py db $2 successful"
                true ;; # Indicates success
            *)
                echo "Dummy manage.py db $2 failed (unknown subcommand)"
                false ;; # Indicates failure
        esac ;;
    create_admin)
        echo "Dummy manage.py create_admin successful with args: $@"
        true ;; # Indicates success
    *)
        echo "Dummy manage.py $1 failed (unknown command)"
        false ;; # Indicates failure
esac
