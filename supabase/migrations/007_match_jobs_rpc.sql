-- RPC function for vector similarity job search.
-- Called from crew.py instead of the keyword-based Python filter.
-- Handles: vector similarity, exclude matched IDs, experience filter, location filter.

create or replace function match_jobs(
  query_embedding   vector(768),
  exclude_ids       uuid[],
  exp_ceiling       float,
  preferred_locs    text[],
  match_count       int default 30
)
returns table (
  id              uuid,
  title           text,
  location        text,
  min_experience  float,
  similarity      float
)
language plpgsql
as $$
begin
  return query
  select
    jl.id,
    jl.title,
    jl.location,
    jl.min_experience,
    1 - (jl.embedding_vector <=> query_embedding) as similarity
  from job_listings jl
  where
    jl.embedding_vector is not null
    and jl.is_live = true
    and not (jl.id = any(exclude_ids))
    and (jl.min_experience is null or jl.min_experience <= exp_ceiling)
    and (
      array_length(preferred_locs, 1) is null
      or exists (
        select 1 from unnest(preferred_locs) pl
        where lower(jl.location) like '%' || lower(pl) || '%'
      )
    )
  order by jl.embedding_vector <=> query_embedding
  limit match_count;
end;
$$;
