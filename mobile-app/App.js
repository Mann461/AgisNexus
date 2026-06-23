// SolarShield AI Mobile App Scaffold (React Native + Expo)
// Designed for field police officers to receive real-time push alerts and locate incidents.

import React, { useState, useEffect } from 'react';
import { StyleSheet, Text, View, FlatList, TouchableOpacity, Alert, SafeAreaView, StatusBar, ActivityIndicator } from 'react-native';

const BACKEND_URL = "http://10.0.2.2:8000/api/v1"; // Loopback for Android emulator
const FALLBACK_URL = "http://localhost:8000/api/v1"; // Fallback for local web/node tests

export default function App() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [connectionStatus, setConnectionStatus] = useState("checking");

  const fetchAlerts = async () => {
    try {
      let response = await fetch(`${BACKEND_URL}/alerts`);
      if (!response.ok) {
        response = await fetch(`${FALLBACK_URL}/alerts`);
      }
      if (response.ok) {
        const data = await response.json();
        setAlerts(data.sort((a, b) => new Date(b.created_at) - new Date(a.created_at)));
        setConnectionStatus("online");
      }
    } catch (e) {
      console.log("Offline mode, loading mock alerts");
      setConnectionStatus("offline");
      // Only set mocks if list is empty to avoid overwriting user resolutions offline
      if (alerts.length === 0) {
        setAlerts([
          { id: '1', alert_type: 'WEAPON DETECTION', threat_level: 'CRITICAL', created_at: new Date().toISOString(), latitude: 23.0225, longitude: 72.5714, status: 'UNRESOLVED' },
          { id: '2', alert_type: 'VIOLENCE IN PUBLIC', threat_level: 'HIGH', created_at: new Date().toISOString(), latitude: 23.0225, longitude: 72.5714, status: 'DISPATCHED' }
        ]);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
    // Poll backend every 4 seconds for fresh dispatch events
    const interval = setInterval(fetchAlerts, 4000);
    return () => clearInterval(interval);
  }, []);

  const handleAcknowledge = (id, type) => {
    Alert.alert(
      "Acknowledge Event",
      `Acknowledge and mark ${type} as resolved?`,
      [
        { text: "Cancel", style: "cancel" },
        { 
          text: "Resolve", 
          onPress: async () => {
            try {
              let response = await fetch(`${BACKEND_URL}/alerts/${id}/status`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: 'RESOLVED' })
              });
              if (!response.ok) {
                response = await fetch(`${FALLBACK_URL}/alerts/${id}/status`, {
                  method: 'PATCH',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ status: 'RESOLVED' })
                });
              }
              if (response.ok) {
                fetchAlerts();
              } else {
                // Local UI fallback state
                setAlerts(prev => prev.map(a => a.id === id ? { ...a, status: 'RESOLVED' } : a));
              }
            } catch (err) {
              // Local UI fallback state
              setAlerts(prev => prev.map(a => a.id === id ? { ...a, status: 'RESOLVED' } : a));
            }
          } 
        }
      ]
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" />
      <View style={styles.header}>
        <View style={styles.titleRow}>
          <Text style={styles.headerTitle}>SolarShield AI - Mobile Command</Text>
          <View style={[styles.statusDot, connectionStatus === 'online' ? styles.dotGreen : styles.dotOrange]} />
        </View>
        <Text style={styles.headerSubtitle}>Field Officer Live Dispatch Feed ({connectionStatus.toUpperCase()})</Text>
      </View>

      {loading && alerts.length === 0 ? (
        <View style={styles.loader}>
          <ActivityIndicator size="large" color="#3b82f6" />
          <Text style={styles.loaderText}>CONNECTING TO DISPATCH CORE...</Text>
        </View>
      ) : (
        <FlatList
          data={alerts}
          keyExtractor={item => item.id}
          contentContainerStyle={styles.listContainer}
          renderItem={({ item }) => {
            const displayType = item.alert_type || item.type;
            const displayLevel = item.threat_level || item.level;
            const displayLocation = item.location || `Lat: ${item.latitude?.toFixed(4)}, Lng: ${item.longitude?.toFixed(4)}`;
            const displayTime = item.time || new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

            return (
              <View style={[styles.card, displayLevel === 'CRITICAL' ? styles.criticalBorder : styles.highBorder]}>
                <View style={styles.cardHeader}>
                  <Text style={styles.alertType}>{displayType}</Text>
                  <Text style={[styles.badge, displayLevel === 'CRITICAL' ? styles.criticalBadge : styles.highBadge]}>
                    {displayLevel}
                  </Text>
                </View>
                
                <View style={styles.cardBody}>
                  <Text style={styles.metaText}>📍 {displayLocation}</Text>
                  <Text style={styles.metaText}>⏰ {displayTime}</Text>
                  <Text style={styles.metaText}>
                    Status: <Text style={[styles.statusHighlight, item.status === 'RESOLVED' ? styles.statusResolved : styles.statusUnresolved]}>{item.status}</Text>
                  </Text>
                </View>

                {item.status !== 'RESOLVED' && (
                  <TouchableOpacity 
                    style={styles.button}
                    onPress={() => handleAcknowledge(item.id, displayType)}
                  >
                    <Text style={styles.buttonText}>Acknowledge & Resolve</Text>
                  </TouchableOpacity>
                )}
              </View>
            );
          }}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#030712', // Dark background matching design system
  },
  header: {
    padding: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#1f2937',
  },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#3b82f6',
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  dotGreen: {
    backgroundColor: '#10b981',
  },
  dotOrange: {
    backgroundColor: '#f59e0b',
  },
  headerSubtitle: {
    fontSize: 11,
    color: '#9ca3af',
    marginTop: 4,
  },
  listContainer: {
    padding: 16,
  },
  loader: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 12,
  },
  loaderText: {
    fontSize: 11,
    color: '#3b82f6',
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  card: {
    backgroundColor: '#111827',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
  },
  criticalBorder: {
    borderColor: 'rgba(239, 68, 68, 0.4)',
  },
  highBorder: {
    borderColor: 'rgba(245, 158, 11, 0.4)',
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottomWidth: 1,
    borderBottomColor: '#1f2937',
    paddingBottom: 10,
    marginBottom: 10,
  },
  alertType: {
    fontSize: 15,
    fontWeight: 'bold',
    color: '#f3f4f6',
  },
  badge: {
    fontSize: 9,
    fontWeight: 'bold',
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 6,
    overflow: 'hidden',
  },
  criticalBadge: {
    backgroundColor: 'rgba(239, 68, 68, 0.2)',
    color: '#ef4444',
  },
  highBadge: {
    backgroundColor: 'rgba(245, 158, 11, 0.2)',
    color: '#f59e0b',
  },
  cardBody: {
    gap: 6,
    marginBottom: 12,
  },
  metaText: {
    color: '#9ca3af',
    fontSize: 13,
  },
  statusHighlight: {
    fontWeight: 'bold',
  },
  statusResolved: {
    color: '#10b981',
  },
  statusUnresolved: {
    color: '#ef4444',
  },
  button: {
    backgroundColor: '#1e3a8a',
    borderColor: '#3b82f6',
    borderWidth: 1,
    padding: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  buttonText: {
    color: '#3b82f6',
    fontWeight: 'bold',
    fontSize: 13,
  }
});
