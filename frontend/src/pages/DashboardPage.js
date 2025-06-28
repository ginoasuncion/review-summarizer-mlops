import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Chip,
  Button,
  Alert,
  CircularProgress,
  List,
  ListItem,
  ListItemText,
  Divider
} from '@mui/material';
import { Refresh, CheckCircle, Error, Schedule } from '@mui/icons-material';
import { checkHealth, listJobs } from '../services/api';

function DashboardPage() {
  const [healthStatus, setHealthStatus] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadDashboard = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const [healthData, jobsData] = await Promise.all([
        checkHealth(),
        listJobs(5)
      ]);
      
      setHealthStatus(healthData);
      setJobs(jobsData.jobs || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
  }, []);

  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy':
        return 'success';
      case 'degraded':
        return 'warning';
      case 'unhealthy':
        return 'error';
      default:
        return 'default';
    }
  };

  const getJobStatusColor = (state) => {
    switch (state) {
      case 'success':
      case 'completed':
        return 'success';
      case 'running':
        return 'info';
      case 'failed':
        return 'error';
      case 'scheduled':
        return 'warning';
      default:
        return 'default';
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          Dashboard
        </Typography>
        <Button
          variant="outlined"
          startIcon={<Refresh />}
          onClick={loadDashboard}
        >
          Refresh
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* System Health */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                System Health
              </Typography>
              {healthStatus && (
                <Box>
                  <Chip
                    icon={healthStatus.status === 'healthy' ? <CheckCircle /> : <Error />}
                    label={`Status: ${healthStatus.status}`}
                    color={getStatusColor(healthStatus.status)}
                    sx={{ mb: 2 }}
                  />
                  <List dense>
                    <ListItem>
                      <ListItemText
                        primary="YouTube Search API"
                        secondary={healthStatus.youtube_search_api || 'Unknown'}
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemText
                        primary="Product Summary API"
                        secondary={healthStatus.product_summary_api || 'Unknown'}
                      />
                    </ListItem>
                  </List>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Recent Jobs */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Recent Jobs
              </Typography>
              {jobs.length > 0 ? (
                <List dense>
                  {jobs.map((job, index) => (
                    <React.Fragment key={job.job_id}>
                      <ListItem>
                        <ListItemText
                          primary={job.job_id}
                          secondary={`Status: ${job.status} | ${job.scheduled_time}`}
                        />
                        <Chip
                          size="small"
                          label={job.state}
                          color={getJobStatusColor(job.state)}
                        />
                      </ListItem>
                      {index < jobs.length - 1 && <Divider />}
                    </React.Fragment>
                  ))}
                </List>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  No recent jobs found
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Quick Actions */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Quick Actions
              </Typography>
              <Box display="flex" gap={2} flexWrap="wrap">
                <Button
                  variant="contained"
                  startIcon={<Schedule />}
                  href="/schedule"
                >
                  Schedule New Job
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<Refresh />}
                  href="/manual"
                >
                  Manual Process
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}

export default DashboardPage; 