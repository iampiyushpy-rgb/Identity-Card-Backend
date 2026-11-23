-- TechRavisha Smart ID Card Suite - MySQL Database Initialization Script
-- Run this in MySQL Workbench, phpMyAdmin, or MySQL CLI:
-- mysql -u root -p < setup_mysql.sql

CREATE DATABASE IF NOT EXISTS techravisha_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE techravisha_db;

-- After creating the database, run the following in your terminal:
-- 1. python manage.py migrate
-- 2. python manage.py loaddata initial_data.json  (to load existing sample data)

