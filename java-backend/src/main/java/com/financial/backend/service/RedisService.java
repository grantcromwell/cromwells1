package com.financial.backend.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.financial.backend.model.EquityData;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import redis.clients.jedis.Jedis;
import redis.clients.jedis.JedisPool;
import redis.clients.jedis.JedisPoolConfig;

import java.io.IOException;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;

public class RedisService {
    private static final Logger logger = LoggerFactory.getLogger(RedisService.class);
    
    private final JedisPool jedisPool;
    private final ObjectMapper objectMapper;
    private final int ttlSeconds;
    
    public RedisService(String host, int port, int tradingDays) {
        JedisPoolConfig poolConfig = new JedisPoolConfig();
        poolConfig.setMaxTotal(10);
        poolConfig.setMaxIdle(5);
        poolConfig.setMinIdle(1);
        poolConfig.setTestOnBorrow(true);
        poolConfig.setTestWhileIdle(true);
        
        this.jedisPool = new JedisPool(poolConfig, host, port);
        this.objectMapper = new ObjectMapper();
        
        this.ttlSeconds = tradingDays * 24 * 60 * 60;
        logger.info("Redis service initialized ({} trading days = {} seconds TTL)", 
                   tradingDays, ttlSeconds);
    }
    
    public void storeBatch(List<EquityData> dataList) {
        try (Jedis jedis = jedisPool.getResource()) {
            redis.clients.jedis.Pipeline pipeline = jedis.pipelined();
            
            for (EquityData data : dataList) {
                String key = generateKey(data.getSymbol(), data.getTimestamp());
                String value = objectMapper.writeValueAsString(data);
                
                pipeline.setex(key, ttlSeconds, value);
                
                String symbolIndexKey = "symbol:" + data.getSymbol();
                pipeline.zadd(symbolIndexKey, data.getTimestamp(), key);
                pipeline.expire(symbolIndexKey, ttlSeconds);
            }
            
            pipeline.sync();
            logger.info("Batch stored {} records with {} day TTL", dataList.size(), ttlSeconds / 86400);
        } catch (IOException e) {
            logger.error("Error: {}", e.getMessage());
        }
    }
    
    public List<EquityData> getEquityDataBySymbol(String symbol, int limit) {
        try (Jedis jedis = jedisPool.getResource()) {
            String pattern = "equity:" + symbol + ":*";
            List<EquityData> results = new ArrayList<>();
            Set<String> keys = jedis.keys(pattern);
            
            if (keys != null && !keys.isEmpty()) {
                List<String> keyList = new ArrayList<>(keys);
                int start = Math.max(0, keyList.size() - limit);
                for (int i = start; i < keyList.size(); i++) {
                    String value = jedis.get(keyList.get(i));
                    if (value != null) {
                        results.add(objectMapper.readValue(value, EquityData.class));
                    }
                }
            }
            
            return results;
        } catch (IOException e) {
            logger.error("Error: {}", e.getMessage());
            return new ArrayList<>();
        }
    }
    
    public List<EquityData> getAllRecentData() {
        List<EquityData> allData = new ArrayList<>();
        String[] symbols = {"MNQ", "NVDA", "AMD", "WDC", "SLV", "GS", "NET", "EWJ", "EURUSD", "INRJPY", "BRLGBP", "STLD", "CRCL", "UBS", "TTWO", "ETHUSD"};
        
        for (String symbol : symbols) {
            allData.addAll(getEquityDataBySymbol(symbol, 100));
        }
        
        return allData;
    }
    
    public void close() {
        if (jedisPool != null) {
            jedisPool.close();
        }
    }
    
    private String generateKey(String symbol, long timestamp) {
        return "equity:" + symbol + ":" + timestamp;
    }
}
