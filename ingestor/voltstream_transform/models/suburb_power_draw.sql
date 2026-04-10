{{ config(materialized='table') }}

with raw_ev_data as (
    -- In dbt, we select from the raw table we built earlier
    select * from VOLTSTREAM_DB.PUBLIC.STG_EV_DATA
),

aggregated as (
    select
        suburb,
        count(station_id) as total_stations,
        -- We only calculate kW draw if the station is actively CHARGING
        sum(case when status = 'CHARGING' then kw_output else 0 end) as active_kw_draw,
        max(recorded_at) as last_updated
    from raw_ev_data
    group by 1
)

select * from aggregated
