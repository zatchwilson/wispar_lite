#!/bin/bash

# Function to create the database and tables
create_db() {
    echo "Creating the database 'wispar_db' and tables..."

    # Log into MariaDB and create database
    mysql -u root -p -e "
        CREATE DATABASE IF NOT EXISTS wispar_db CHARACTER SET utf8;"
    echo "Database 'wispar_db' created successfully."
}

start_mariadb() {
    # Start mariadb and enable service
    sudo systemctl start mariadb

    # uncomment this line below if you want mariadb to start every time that your computer/linux system boots up
    # sudo systemctl enable mariadb

    # Set a root password for MariaDB
    echo "changing password for root"
    sudo mysql -u root -e "SET PASSWORD FOR 'root'@'localhost' = PASSWORD('password');" # change the text in the quotes where it currently is all lower case 'password' to whatever password you'd like

    # Remove test databases (optional), we don't need to worry about this for now.
    # sudo mysql -u root -e "DROP DATABASE IF EXISTS test;"
    # sudo mysql -u root -e "DELETE FROM mysql.db WHERE Db='test' OR Db='test_%';"

    # Reload privileges
    sudo mysql -u root -e "FLUSH PRIVILEGES;"

    echo "MariaDB started and secured successfully."
}

# Main script logic
OS_NAME=$(uname -s)
if [[ "$OS_NAME" == "Linux" ]]; then
    # Ensure MariaDB is running
    start_mariadb
    if systemctl status mariadb | grep -q "active (running)"; then

        # Log in as root and create the database, otherwise tell user it failed
        if ! create_db; then
            echo 'Failed to create database'
            return 1
        fi
    else
        echo "MariaDB is not running. Please start MariaDB and try again."
        exit 1
    fi
    echo 'Setup complete.'
fi
