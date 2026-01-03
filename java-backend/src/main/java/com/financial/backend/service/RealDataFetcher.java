package com.financial.backend.service;

import com.financial.backend.model.EquityData;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;

public class RealDataFetcher {
    private static final Logger logger = LoggerFactory.getLogger(RealDataFetcher.class);
    private static final String YAHOO_BASE_URL = "https://query1.finance.yahoo.com/v7/finance/download/";
    
    public List<EquityData> fetchStockData(String symbol, int days) {
        List<EquityData> data = new ArrayList<>();
        
        try {
            LocalDate endDate = LocalDate.now();
            LocalDate startDate = endDate.minusDays(days * 24 / 18 * 7);
            
            String urlStr = String.format("%s%s?period1=%d&period2=%d&interval=1d&events=history",
                YAHOO_BASE_URL, symbol, 
                startDate.atStartOfDay().toEpochSecond(java.time.ZoneOffset.UTC),
                endDate.atStartOfDay().toEpochSecond(java.time.ZoneOffset.UTC));
            
            logger.debug("Fetching stock data for {}: {}", symbol, urlStr);
            
            URL url = new URL(urlStr);
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("GET");
            conn.setConnectTimeout(10000);
            conn.setReadTimeout(10000);
            
            int responseCode = conn.getResponseCode();
            
            if (responseCode == 200) {
                try (BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()))) {
                    String line = reader.readLine();
                    if (line != null && line.contains("Date")) {
                        while ((line = reader.readLine()) != null && !line.isEmpty()) {
                            String[] parts = line.split(",");
                            if (parts.length >= 6) {
                                EquityData eq = parseStockCSVLine(symbol, parts);
                                if (eq != null) {
                                    data.add(eq);
                                }
                            }
                        }
                    }
                }
                logger.info("Fetched {} records for {}", data.size(), symbol);
            } else {
                logger.warn("Failed to fetch {}: HTTP {}", symbol, responseCode);
            }
            
            conn.disconnect();
            
        } catch (Exception e) {
            logger.warn("Error fetching {}: {}, using simulated data", symbol, e.getMessage());
        }
        
        return data;
    }
    
    public List<EquityData> fetchForexData(String symbol, int days) {
        List<EquityData> data = new ArrayList<>();
        
        try {
            LocalDate endDate = LocalDate.now();
            LocalDate startDate = endDate.minusDays(days * 24 / 18 * 7);
            
            String urlStr = String.format("%s%s?period1=%d&period2=%d&interval=1d&events=history",
                YAHOO_BASE_URL, symbol,
                startDate.atStartOfDay().toEpochSecond(java.time.ZoneOffset.UTC),
                endDate.atStartOfDay().toEpochSecond(java.time.ZoneOffset.UTC));
            
            logger.debug("Fetching forex data for {}: {}", symbol, urlStr);
            
            URL url = new URL(urlStr);
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("GET");
            conn.setConnectTimeout(10000);
            conn.setReadTimeout(10000);
            
            int responseCode = conn.getResponseCode();
            
            if (responseCode == 200) {
                try (BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()))) {
                    String line = reader.readLine();
                    if (line != null && line.contains("Date")) {
                        while ((line = reader.readLine()) != null && !line.isEmpty()) {
                            String[] parts = line.split(",");
                            if (parts.length >= 6) {
                                EquityData eq = parseForexCSVLine(symbol, parts);
                                if (eq != null) {
                                    data.add(eq);
                                }
                            }
                        }
                    }
                }
                logger.info("Fetched {} records for forex {}", data.size(), symbol);
            }
            
            conn.disconnect();
            
        } catch (Exception e) {
            logger.warn("Error fetching forex {}: {}", symbol, e.getMessage());
        }
        
        return data;
    }
    
    public List<EquityData> fetchCryptoData(String symbol, int days) {
        List<EquityData> data = new ArrayList<>();
        
        try {
            LocalDate endDate = LocalDate.now();
            LocalDate startDate = endDate.minusDays(days * 24 / 18 * 7);
            
            String urlStr = String.format("%s%s?period1=%d&period2=%d&interval=1d&events=history",
                YAHOO_BASE_URL, symbol,
                startDate.atStartOfDay().toEpochSecond(java.time.ZoneOffset.UTC),
                endDate.atStartOfDay().toEpochSecond(java.time.ZoneOffset.UTC));
            
            logger.debug("Fetching crypto data for {}: {}", symbol, urlStr);
            
            URL url = new URL(urlStr);
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("GET");
            conn.setConnectTimeout(10000);
            conn.setReadTimeout(10000);
            
            int responseCode = conn.getResponseCode();
            
            if (responseCode == 200) {
                try (BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()))) {
                    String line = reader.readLine();
                    if (line != null && line.contains("Date")) {
                        while ((line = reader.readLine()) != null && !line.isEmpty()) {
                            String[] parts = line.split(",");
                            if (parts.length >= 6) {
                                EquityData eq = parseCryptoCSVLine(symbol, parts);
                                if (eq != null) {
                                    data.add(eq);
                                }
                            }
                        }
                    }
                }
                logger.info("Fetched {} records for crypto {}", data.size(), symbol);
            }
            
            conn.disconnect();
            
        } catch (Exception e) {
            logger.warn("Error fetching crypto {}: {}", symbol, e.getMessage());
        }
        
        return data;
    }
    
    private EquityData parseStockCSVLine(String symbol, String[] parts) {
        try {
            DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd");
            LocalDate date = LocalDate.parse(parts[0], formatter);
            long timestamp = date.atStartOfDay().toEpochSecond(java.time.ZoneOffset.UTC) * 1000;
            
            double open = Double.parseDouble(parts[1]);
            double high = Double.parseDouble(parts[2]);
            double low = Double.parseDouble(parts[3]);
            double close = Double.parseDouble(parts[4]);
            double volume = Double.parseDouble(parts[5]);
            
            if (close > 0 && volume > 0) {
                return new EquityData(symbol, timestamp, open, high, low, close, volume, close);
            }
        } catch (Exception e) {
            logger.debug("Error parsing line: {}", e.getMessage());
        }
        return null;
    }
    
    private EquityData parseForexCSVLine(String symbol, String[] parts) {
        try {
            DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd");
            LocalDate date = LocalDate.parse(parts[0], formatter);
            long timestamp = date.atStartOfDay().toEpochSecond(java.time.ZoneOffset.UTC) * 1000;
            
            double open = Double.parseDouble(parts[1]);
            double high = Double.parseDouble(parts[2]);
            double low = Double.parseDouble(parts[3]);
            double close = Double.parseDouble(parts[4]);
            double volume = Double.parseDouble(parts[5]);
            
            String cleanSymbol = symbol.replace("=X", "");
            
            if (close > 0) {
                return new EquityData(cleanSymbol, timestamp, open, high, low, close, volume * 10000, close);
            }
        } catch (Exception e) {
            logger.debug("Error parsing forex line: {}", e.getMessage());
        }
        return null;
    }
    
    private EquityData parseCryptoCSVLine(String symbol, String[] parts) {
        try {
            DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd");
            LocalDate date = LocalDate.parse(parts[0], formatter);
            long timestamp = date.atStartOfDay().toEpochSecond(java.time.ZoneOffset.UTC) * 1000;
            
            double open = Double.parseDouble(parts[1]);
            double high = Double.parseDouble(parts[2]);
            double low = Double.parseDouble(parts[3]);
            double close = Double.parseDouble(parts[4]);
            double volume = Double.parseDouble(parts[5]);
            
            String cleanSymbol = symbol.replace("-USD", "USD");
            
            if (close > 0) {
                return new EquityData(cleanSymbol, timestamp, open, high, low, close, volume, close);
            }
        } catch (Exception e) {
            logger.debug("Error parsing crypto line: {}", e.getMessage());
        }
        return null;
    }
}
