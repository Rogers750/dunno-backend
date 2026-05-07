-- Add exp_floor param to match_jobs so user's min_experience preference is a hard filter.

create or replace function match_jobs(
  query_embedding   vector(1024),
  exclude_ids       uuid[],
  exp_floor         float default 0,
  exp_ceiling       float default 99,
  preferred_locs    text[] default array[]::text[],
  match_count       int default 50,
  min_similarity    float default 0.3
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
    and (jl.min_experience is null or jl.min_experience >= exp_floor)
    and (jl.min_experience is null or jl.min_experience <= exp_ceiling)
    and (1 - (jl.embedding_vector <=> query_embedding)) >= min_similarity
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
