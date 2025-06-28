import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Grid,
  IconButton,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Alert,
  CircularProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem
} from '@mui/material';
import { Add, Delete, Schedule } from '@mui/icons-material';
import { scheduleAutomation } from '../services/api';

function SchedulePage() {
  const [shoes, setShoes] = useState([
    { name: '', max_results: 3 }
  ]);
  const [waitMinutes, setWaitMinutes] = useState(1);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [startTime, setStartTime] = useState('');

  const addShoe = () => {
    setShoes([...shoes, { name: '', max_results: 3 }]);
  };

  const removeShoe = (index) => {
    if (shoes.length > 1) {
      const newShoes = shoes.filter((_, i) => i !== index);
      setShoes(newShoes);
    }
  };

  const updateShoe = (index, field, value) => {
    const newShoes = [...shoes];
    newShoes[index][field] = value;
    setShoes(newShoes);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Validate form
    const validShoes = shoes.filter(shoe => shoe.name.trim() !== '');
    if (validShoes.length === 0) {
      setError('Please add at least one shoe');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      let start_time;
      if (startTime) {
        // Convert Bangkok time (UTC+7) to UTC ISO string
        const localDate = new Date(startTime);
        const bangkokOffset = 7 * 60; // minutes
        const utcDate = new Date(localDate.getTime() - (bangkokOffset * 60 * 1000));
        start_time = utcDate.toISOString();
      }
      const response = await scheduleAutomation(validShoes, waitMinutes, start_time);
      setResult(response);
      setShoes([{ name: '', max_results: 3 }]); // Reset form
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box>
      <Typography variant="h5" component="h1" gutterBottom>
        Schedule Automation
      </Typography>

      <Card>
        <CardContent>
          <form onSubmit={handleSubmit}>
            <Grid container spacing={3}>
              {/* Shoes List */}
              <Grid item xs={12}>
                <Typography variant="h6" gutterBottom>
                  Shoes to Process
                </Typography>
                <List>
                  {shoes.map((shoe, index) => (
                    <ListItem key={index} sx={{ border: '1px solid #e0e0e0', borderRadius: 1, mb: 1 }}>
                      <ListItemText
                        primary={
                          <TextField
                            fullWidth
                            label="Shoe Name"
                            value={shoe.name}
                            onChange={(e) => updateShoe(index, 'name', e.target.value)}
                            placeholder="e.g., Nike Air Jordan 1"
                            required
                          />
                        }
                        secondary={
                          <Box mt={1}>
                            <FormControl fullWidth size="small">
                              <InputLabel>Max Results</InputLabel>
                              <Select
                                value={shoe.max_results}
                                label="Max Results"
                                onChange={(e) => updateShoe(index, 'max_results', Number(e.target.value))}
                              >
                                <MenuItem value={3}>3 videos</MenuItem>
                              </Select>
                            </FormControl>
                          </Box>
                        }
                      />
                      <ListItemSecondaryAction>
                        <IconButton
                          edge="end"
                          onClick={() => removeShoe(index)}
                          disabled={shoes.length === 1}
                        >
                          <Delete />
                        </IconButton>
                      </ListItemSecondaryAction>
                    </ListItem>
                  ))}
                </List>
                
                <Button
                  startIcon={<Add />}
                  onClick={addShoe}
                  variant="outlined"
                  sx={{ mt: 2 }}
                >
                  Add Another Shoe
                </Button>
              </Grid>

              {/* Wait Time and Start Time (Bangkok) */}
              <Grid item xs={12} md={6}>
                <FormControl fullWidth>
                  <InputLabel>Wait Time</InputLabel>
                  <Select
                    value={waitMinutes}
                    label="Wait Time"
                    onChange={(e) => setWaitMinutes(Number(e.target.value))}
                  >
                    <MenuItem value={1}>1 minute</MenuItem>
                    <MenuItem value={5}>5 minutes</MenuItem>
                    <MenuItem value={10}>10 minutes</MenuItem>
                  </Select>
                </FormControl>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  Time to wait between YouTube search and product summary generation
                </Typography>
                <label htmlFor="start-time-picker" style={{ display: 'block', marginTop: 16, marginBottom: 8 }}>
                  Start Time (Bangkok, UTC+7):
                </label>
                <input
                  id="start-time-picker"
                  type="datetime-local"
                  value={startTime}
                  onChange={e => setStartTime(e.target.value)}
                  style={{ width: '100%', padding: 8, fontSize: 16 }}
                />
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  Leave blank to start immediately
                </Typography>
              </Grid>

              {/* Submit Button */}
              <Grid item xs={12}>
                <Button
                  type="submit"
                  variant="contained"
                  size="large"
                  startIcon={loading ? <CircularProgress size={20} /> : <Schedule />}
                  disabled={loading}
                  fullWidth
                >
                  {loading ? 'Scheduling...' : 'Schedule Job'}
                </Button>
              </Grid>
            </Grid>
          </form>
        </CardContent>
      </Card>

      {/* Results */}
      {result && (
        <Alert severity="success" sx={{ mt: 3 }}>
          <Typography variant="h6">Job Scheduled Successfully!</Typography>
          <Typography variant="body2">
            Job ID: {result.job_id}
          </Typography>
          <Typography variant="body2">
            Status: {result.status}
          </Typography>
          <Typography variant="body2">
            Shoes: {result.shoes_count}
          </Typography>
          <Typography variant="body2">
            Scheduled: {new Date(result.scheduled_time).toLocaleString()}
          </Typography>
        </Alert>
      )}

      {error && (
        <Alert severity="error" sx={{ mt: 3 }}>
          {error}
        </Alert>
      )}
    </Box>
  );
}

export default SchedulePage; 