package com.financial.backend;

import com.financial.backend.api.EquityApiServer;
import com.financial.backend.model.EquityData;
import com.financial.backend.processor.FeatureEngineer;
import com.financial.backend.service.RedisService;
import com.financial.backend.service.RealDataFetcher;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Timer;
import java.util.TimerTask;

public class Main {
    private static final Logger logger = LoggerFactory.getLogger(Main.class);
    
    private static final String[] SYMBOLS = {"NVDA", "AMD", "GS", "SLV", "NET", "WDC", "CRCL"};
    private static final String FOREX_SYMBOLS[] = {"EURUSD=X", "INRJPY=X", "BRLGBP=X"};
    private static final String INDEX_SYMBOLS[] = {"MNQ", "EWJ"};
    private static final String CRYPTO_SYMBOLS[] = {"ETH-USD"};
    private static final String ADDITIONAL_SYMBOLS[] = {"STLD", "TTWO", "UBS"};
    
    private static final String REDIS_HOST = "localhost";
    private static final int REDIS_PORT = 6379;
    private static final int TRADING_DAYS = 100;
    
    public static void main(String[] args) {
        logger.info("Starting Financial Forecasting System - Real Data Mode ({} trading days)", TRADING_DAYS);
        
        RedisService redisService = new RedisService(REDIS_HOST, REDIS_PORT, TRADING_DAYS);
        RealDataFetcher dataFetcher = new RealDataFetcher();
        FeatureEngineer featureEngineer = new FeatureEngineer();
        
        try {
            EquityApiServer apiServer = new EquityApiServer(redisService);
            apiServer.start();
            
            logger.info("Fetching real historical data from Yahoo Finance...");
            ingestRealData(redisService, dataFetcher, featureEngineer);
            
            Timer dataIngestionTimer = new Timer("DataIngestion", true);
            dataIngestionTimer.schedule(new TimerTask() {
                @Override
                public void run() {
                    ingestDailyData(redisService, featureEngineer);
                }
            }, 0, 60000);
            
            Timer cleanupTimer = new Timer("Cleanup", true);
            cleanupTimer.schedule(new TimerTask() {
                @Override
                public void run() {
                    logger.info("{}-day trading window active - oldest data auto-expires", TRADING_DAYS);
                }
            }, 0, 3600000);
            
            logger.info("System started. {} trading day window. Ctrl+C to stop.", TRADING_DAYS);
            
            Runtime.getRuntime().addShutdownHook(new Thread(() -> {
                logger.info("Shutting down...");
                apiServer.stop();
                redisService.close();
                dataIngestionTimer.cancel();
                cleanupTimer.cancel();
            }));
            
        } catch (IOException e) {
            logger.error("Failed to start: {}", e.getMessage());
            System.exit(1);
        }
    }
    
    private static void ingestRealData(RedisService redisService, RealDataFetcher dataFetcher, FeatureEngineer featureEngineer) {
        try {
            List<EquityData> allData = new ArrayList<>();
            
            logger.info("Fetching stocks...");
            for (String symbol : SYMBOLS) {
                List<EquityData> data = dataFetcher.fetchStockData(symbol, TRADING_DAYS);
                if (!data.isEmpty()) {
                    allData.addAll(data);
                    logger.info("  {}: {} records", symbol, data.size());
                }
            }
            
            logger.info("Fetching forex...");
            for (String symbol : FOREX_SYMBOLS) {
                List<EquityData> data = dataFetcher.fetchForexData(symbol, TRADING_DAYS);
                if (!data.isEmpty()) {
                    allData.addAll(data);
                    String cleanSymbol = symbol.replace("=X", "");
                    logger.info("  {}: {} records", cleanSymbol, data.size());
                }
            }
            
            logger.info("Fetching crypto...");
            for (String symbol : CRYPTO_SYMBOLS) {
                List<EquityData> data = dataFetcher.fetchCryptoData(symbol, TRADING_DAYS);
                if (!data.isEmpty()) {
                    allData.addAll(data);
                    String cleanSymbol = symbol.replace("-USD", "USD");
                    logger.info("  {}: {} records", cleanSymbol, data.size());
                }
            }
            
            if (allData.isEmpty()) {
                logger.warn("No real data fetched, using simulated data");
                allData = generateSimulatedData();
            }
            
            redisService.storeBatch(allData);
            logger.info("Total records ingested: {} ({} trading days)", allData.size(), TRADING_DAYS);
            
        } catch (Exception e) {
            logger.error("Error ingesting real data: {}", e.getMessage());
            logger.info("Falling back to simulated data...");
            List<EquityData> simulatedData = generateSimulatedData();
            redisService.storeBatch(simulatedData);
            logger.info("Ingested {} simulated records", simulatedData.size());
        }
    }
    
    private static void ingestDailyData(RedisService redisService, FeatureEngineer featureEngineer) {
        try {
            List<EquityData> sampleData = generateDailyData();
            List<EquityData> engineeredData = featureEngineer.engineerFeatures(sampleData);
            redisService.storeBatch(engineeredData);
            logger.info("Ingested {} daily records", engineeredData.size());
        } catch (Exception e) {
            logger.error("Error ingesting daily data: {}", e.getMessage());
        }
    }
    
    private static List<EquityData> generateSimulatedData() {
        List<EquityData> data = new ArrayList<>();
        long currentTime = System.currentTimeMillis();
        long oneDay = 24 * 60 * 60 * 1000L;
        
        String[] allSymbols = {"NVDA", "AMD", "GS", "SLV", "NET", "WDC", "CRCL", "EWJ", "MNQ", "STLD", "TTWO", "UBS", "EURUSD", "INRJPY", "BRLGBP", "ETHUSD"};
        double[] basePrices = {496.31, 150.55, 351.46, 25.59, 78.47, 60.72, 35.20, 65.77, 16202.41, 53.20, 137.50, 28.40, 1.08, 1.82, 0.25, 3205.00};
        double[] volatilities = {0.028, 0.025, 0.018, 0.022, 0.026, 0.023, 0.030, 0.015, 0.012, 0.024, 0.020, 0.017, 0.006, 0.007, 0.008, 0.038};
        
        for (int s = 0; s < allSymbols.length; s++) {
            String symbol = allSymbols[s];
            double basePrice = basePrices[s];
            double volatility = volatilities[s];
            double trend = (s < 4) ? 0.0003 : ((s > 8) ? -0.0001 : 0.0001);
            
            for (int i = 0; i < TRADING_DAYS; i++) {
                long timestamp = currentTime - (TRADING_DAYS - 1 - i) * oneDay;
                
                double cumulativeTrend = trend * i;
                double noise = (Math.random() - 0.5) * basePrice * volatility;
                double priceChange = noise + (cumulativeTrend * basePrice);
                
                double open = basePrice + priceChange;
                double close = open + (Math.random() - 0.5) * basePrice * volatility * 0.5;
                double high = Math.max(open, close) + Math.random() * basePrice * volatility * 0.25;
                double low = Math.min(open, close) - Math.random() * basePrice * volatility * 0.25;
                double volume = 1000000 + Math.random() * 4000000;
                
                EquityData eq = new EquityData(symbol, timestamp, open, high, low, close, volume, close);
                data.add(eq);
            }
        }
        
        return data;
    }
    
    private static List<EquityData> generateDailyData() {
        List<EquityData> data = new ArrayList<>();
        long currentTime = System.currentTimeMillis();
        long oneDay = 24 * 60 * 60 * 1000;
        
        String[] allSymbols = {"NVDA", "AMD", "GS", "SLV", "NET", "WDC", "CRCL", "EWJ", "MNQ", "STLD", "TTWO", "UBS", "EURUSD", "INRJPY", "BRLGBP", "ETHUSD"};
        double[] basePrices = {496.31, 150.55, 351.46, 25.59, 78.47, 60.72, 35.20, 65.77, 16202.41, 53.20, 137.50, 28.40, 1.08, 1.82, 0.25, 3205.00};
        
        for (int i = 0; i < allSymbols.length; i++) {
            String symbol = allSymbols[i];
            double basePrice = basePrices[i];
            double volatility = 0.02;
            double trend = 0.0001;
            
            double priceChange = (Math.random() - 0.5) * basePrice * volatility + (trend * basePrice);
            double open = basePrice + priceChange;
            double close = open + (Math.random() - 0.5) * basePrice * 0.015;
            double high = Math.max(open, close) + Math.random() * basePrice * 0.01;
            double low = Math.min(open, close) - Math.random() * basePrice * 0.01;
            double volume = 1000000 + Math.random() * 4000000;
            
            EquityData eq = new EquityData(symbol, currentTime, open, high, low, close, volume, close);
            data.add(eq);
        }
        
        return data;
    }
}
