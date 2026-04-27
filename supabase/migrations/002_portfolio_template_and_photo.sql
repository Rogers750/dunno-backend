-- Migration 002: add selected_template to portfolios and photo_url to profiles

alter table portfolios
  add column if not exists selected_template text default 'executive_minimal';

alter table profiles
  add column if not exists photo_url text;
