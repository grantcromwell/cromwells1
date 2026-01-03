use rust_model::{ModelPipeline, EquityData};
use std::collections::HashMap;
use redis::RedisResult;

#[derive(Debug, serde::Deserialize)]
struct RedisEquityData {
    symbol: String,
    timestamp: u64,
    open: f64,
    high: f64,
    low: f64,
    close: f64,
    volume: i64,
}

fn main() {
    println!("Financial Forecasting Model Pipeline");
    println!("=====================================\n");
    
    println!("Fetching real historical data from Redis...");
    let data_by_symbol = fetch_from_redis();
    
    let total_records: usize = data_by_symbol.values().map(|v| v.len()).sum();
    println!("Loaded {} records for {} symbols\n", 
             total_records, data_by_symbol.len());
    
    if total_records == 0 {
        println!("No data found in Redis! Please run download_historical.py first.");
        std::process::exit(1);
    }
    
    let days = 240; // 240-day analysis window
    run_analysis(&data_by_symbol, days);
}

fn fetch_from_redis() -> HashMap<String, Vec<EquityData>> {
    let client = redis::Client::open("redis://localhost").expect("Failed to connect to Redis");
    let mut con = client.get_connection().expect("Failed to get Redis connection");
    
    let symbols = vec![
        "MNQ", "NVDA", "AMD", "WDC", "SLV", 
        "GS", "NET", "EWJ", "EURUSD", "INRJPY", 
        "STLD", "CRCL", "UBS", "TTWO", "ETHUSD"
    ];
    
    let mut data_by_symbol: HashMap<String, Vec<EquityData>> = HashMap::new();
    
    for symbol in &symbols {
        println!("Fetching {} from Redis...", symbol);
        
        let pattern = format!("equity:{}:*", symbol);
        let keys: Vec<String> = redis::cmd("KEYS")
            .arg(&pattern)
            .query(&mut con)
            .expect("Failed to fetch keys");
        
        if keys.is_empty() {
            println!("  No data found for {}", symbol);
            continue;
        }
        
        // Get values for all keys
        let mut values: Vec<(String, String)> = Vec::new();
        for key in &keys {
            let value: String = redis::cmd("GET")
                .arg(key)
                .query(&mut con)
                .expect("Failed to get value");
            values.push((key.clone(), value));
        }
        
        // Sort by timestamp
        values.sort_by_key(|(k, _)| {
            let parts: Vec<&str> = k.split(':').collect();
            parts[2].parse::<u64>().unwrap_or(0)
        });
        
        let mut data = Vec::new();
        for (key, value) in &values {
            match serde_json::from_str::<RedisEquityData>(value) {
                Ok(redis_data) => {
                    let equity = EquityData {
                        symbol: redis_data.symbol,
                        timestamp: redis_data.timestamp as i64,
                        open: redis_data.open,
                        high: redis_data.high,
                        low: redis_data.low,
                        close: redis_data.close,
                        volume: redis_data.volume as f64,
                        adjusted_close: redis_data.close,
                        moving_averages: None,
                        rsi: None,
                        macd: None,
                    };
                    data.push(equity);
                }
                Err(e) => {
                    println!("  Failed to parse {}: {}", key, e);
                }
            }
        }
        
        if !data.is_empty() {
            println!("  Loaded {} records", data.len());
            data_by_symbol.insert(symbol.to_string(), data);
        }
    }
    
    data_by_symbol
}

fn run_analysis(data_by_symbol: &HashMap<String, Vec<EquityData>>, days: i64) {
    let mut pipeline = ModelPipeline::new();
    
    println!("Training models on real historical data ({} days)...", days);
    pipeline.train(data_by_symbol);
    println!("Training complete!\n");
    
    let window_label = match days {
        50 => "50-Day",
        100 => "100-Day",
        _ => &format!("{}-Day", days),
    };
    
    println!("=== Strongest Movers (Alpha Search - Real Data) ===");
    let strongest_movers = pipeline.get_strongest_movers(data_by_symbol);
    for result in &strongest_movers {
        let prob_pct = result.probability * 100.0;
        let change_pct = result.change;
        println!("Symbol: {:<8} | Alpha: {:>8.4} | Probability: {:>6.2}% | Change: {:>7.2}%", 
                 result.symbol, result.alpha, prob_pct, change_pct);
    }
    
    println!("\n=== Highest Volume ===");
    let highest_volume = pipeline.get_highest_volume(data_by_symbol);
    for result in &highest_volume {
        println!("Symbol: {:<8} | Volume: {:>12.0} | Alpha: {:>8.4}", 
                 result.symbol, result.volume, result.alpha);
    }
    
    println!("\n=== Highest Probable Alpha (Gaussian Copula - Real Data) ===");
    let probable_alpha = pipeline.get_highest_probable_alpha(data_by_symbol);
    for result in &probable_alpha {
        let prob_pct = result.probability * 100.0;
        let change_pct = result.change;
        println!("Symbol: {:<8} | Alpha: {:>8.4} | Probability: {:>6.2}% | Change: {:>7.2}%", 
                 result.symbol, result.alpha, prob_pct, change_pct);
    }
    
    let corr_analysis = pipeline.get_correlation_analysis();
    println!("\n=== Correlation Analysis ({} Window - Real Data) ===", window_label);
    println!("Matrix Size: {}", corr_analysis.matrix_size);
    println!("Highest Correlation: {:.4}", corr_analysis.highest_correlation);
    println!("Lowest Correlation: {:.4}", corr_analysis.lowest_correlation);
    
    println!("\nPipeline execution complete!");
}
