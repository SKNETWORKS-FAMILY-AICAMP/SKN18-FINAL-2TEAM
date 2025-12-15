// Table Modal Component JavaScript Logic
console.log('[TableModal] ===== Script file loading... =====');

(function() {
    'use strict';
    
    console.log('[TableModal] IIFE starting...');

    // State variables
    let tableRows = 3;
    let tableCols = 3;
    let tableData = [];
    let isInitialized = false;

    // DOM elements
    const modalId = 'tableModal';
    let tableRowsInput = null;
    let tableColsInput = null;
    let tableBody = null;
    let tableDataSection = null;
    let attachTableBtn = null;

    // Get DOM elements
    function getTableModalElements() {
        tableRowsInput = document.getElementById('tableRows');
        tableColsInput = document.getElementById('tableCols');
        tableBody = document.getElementById('tableBody');
        tableDataSection = document.getElementById('tableDataSection');
        attachTableBtn = document.getElementById('attachTableBtn');
    }

    // Initialize modal
    function initTableModal() {
        if (isInitialized) return true;
        
        const modal = document.getElementById(modalId);
        if (!modal) {
            console.warn('[TableModal] Modal element not found');
            return false;
        }
        
        // Get DOM elements
        getTableModalElements();
        
        // Close button handlers
        const closeBtns = modal.querySelectorAll('[data-action="close"]');
        closeBtns.forEach(btn => {
            btn.addEventListener('click', closeTableModal);
        });
        
        // Attach button handler
        if (attachTableBtn) {
            attachTableBtn.addEventListener('click', handleAttachTable);
        }
        
        // Table size inputs - wait for Shoelace components to be ready
        if (typeof customElements !== 'undefined' && customElements.whenDefined) {
            customElements.whenDefined('sl-input').then(() => {
                if (tableRowsInput) {
                    tableRowsInput.addEventListener('sl-input', (e) => {
                        const newRows = parseInt(e.target.value) || 1;
                        setTableRows(newRows);
                        initializeTable(newRows, tableCols);
                    });
                }
                
                if (tableColsInput) {
                    tableColsInput.addEventListener('sl-input', (e) => {
                        const newCols = parseInt(e.target.value) || 1;
                        setTableCols(newCols);
                        initializeTable(tableRows, newCols);
                    });
                }
            }).catch(err => {
                console.warn('[TableModal] Shoelace sl-input not available:', err);
            });
        }
        
        isInitialized = true;
        console.log('[TableModal] Initialized successfully');
        return true;
    }

    // Set table rows
    function setTableRows(rows) {
        tableRows = Math.max(1, Math.min(20, rows));
        if (tableRowsInput) {
            tableRowsInput.value = tableRows;
        }
    }

    // Set table cols
    function setTableCols(cols) {
        tableCols = Math.max(1, Math.min(20, cols));
        if (tableColsInput) {
            tableColsInput.value = tableCols;
        }
    }

    // Initialize table data
    function initializeTable(rows, cols) {
        const rowCount = rows || tableRows;
        const colCount = cols || tableCols;
        const newData = [];
        
        for (let i = 0; i < rowCount; i++) {
            const row = [];
            for (let j = 0; j < colCount; j++) {
                // Keep existing data if available
                const currentRow = Array.isArray(tableData[i]) ? tableData[i] : [];
                const existingValue = currentRow[j] !== undefined ? currentRow[j] : '';
                row.push(existingValue);
            }
            newData.push(row);
        }
        
        tableData = newData;
        renderTable();
    }

    // Render table
    function renderTable() {
        if (!tableBody) {
            getTableModalElements();
        }
        if (!tableBody) return;
        
        tableBody.innerHTML = '';
        
        if (tableData.length === 0) {
            if (tableDataSection) {
                tableDataSection.style.display = 'none';
            }
            return;
        }
        
        if (tableDataSection) {
            tableDataSection.style.display = 'block';
        }
        
        tableData.forEach((row, rowIndex) => {
            const tr = document.createElement('tr');
            
            row.forEach((cell, colIndex) => {
                const td = document.createElement('td');
                const input = document.createElement('input');
                input.type = 'text';
                input.value = cell;
                input.placeholder = `R${rowIndex + 1}C${colIndex + 1}`;
                input.addEventListener('input', (e) => {
                    handleTableCellChange(rowIndex, colIndex, e.target.value);
                });
                td.appendChild(input);
                tr.appendChild(td);
            });
            
            tableBody.appendChild(tr);
        });
    }

    // Handle table cell change
    function handleTableCellChange(rowIndex, colIndex, value) {
        if (!tableData[rowIndex]) {
            tableData[rowIndex] = [];
        }
        tableData[rowIndex][colIndex] = value;
    }

    // Handle attach table
    function handleAttachTable() {
        const tableInfo = {
            id: Date.now(),
            rows: tableRows,
            cols: tableCols,
            data: tableData
        };
        
        // Dispatch event to chat.js
        const event = new CustomEvent('table:attached', {
            detail: tableInfo
        });
        document.dispatchEvent(event);
        
        // Reset and close
        resetTableModal();
        closeTableModal();
    }

    // Reset table modal
    function resetTableModal() {
        tableRows = 3;
        tableCols = 3;
        tableData = [];
        
        if (tableRowsInput) {
            tableRowsInput.value = tableRows;
        }
        if (tableColsInput) {
            tableColsInput.value = tableCols;
        }
        
        renderTable();
    }

    // Open table modal
    function openTableModal() {
        // Ensure initialization
        if (!isInitialized) {
            initTableModal();
        }
        
        const modal = document.getElementById(modalId);
        if (!modal) {
            console.error('[TableModal] Modal element not found');
            return;
        }
        
        // Ensure elements are available
        if (!tableBody || !tableDataSection) {
            getTableModalElements();
        }
        
        // Initialize table if empty
        if (tableData.length === 0) {
            initializeTable(tableRows, tableCols);
        }
        
        modal.classList.add('active');
        console.log('[TableModal] Modal opened');
    }

    // Close table modal
    function closeTableModal() {
        const modal = document.getElementById(modalId);
        if (!modal) return;
        
        modal.classList.remove('active');
        resetTableModal();
    }

    // Export to window immediately
    console.log('[TableModal] Assigning window.TableModal...');
    window.TableModal = {
        open: openTableModal,
        close: closeTableModal,
        reset: resetTableModal,
        init: initTableModal,
        isReady: function() {
            return isInitialized;
        }
    };
    console.log('[TableModal] window.TableModal assigned:', window.TableModal);
    console.log('[TableModal] window.TableModal.open:', typeof window.TableModal.open);

    // Initialize when DOM is ready
    function tryInit() {
        if (initTableModal()) {
            document.dispatchEvent(new Event('tableModal:ready'));
            return true;
        }
        return false;
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            if (!tryInit()) {
                setTimeout(tryInit, 100);
            }
        });
    } else {
        // DOM already ready
        if (!tryInit()) {
            setTimeout(tryInit, 100);
        }
    }

    console.log('[TableModal] Script loaded, window.TableModal available');
})();
